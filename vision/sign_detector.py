"""
vision/sign_detector.py — Process 2: YOLO/Classifier Sign Detection.

Runs on Core 1. Reads frames from shared memory (written by P1),
runs sign classification, writes sign_id / sign_confidence to shared memory.

Target rate: ~10-15 FPS.
"""

from multiprocessing import Value, Lock


def sign_detection_process(
    sign_id: Value,           # c_int — write (SignType enum)
    sign_confidence: Value,   # c_double — write
    system_running: Value,    # c_bool — read
    shm_name: str,            # SharedMemory name — read frames from P1
    frame_lock: Lock,         # synchronize
    frame_width: int,
    frame_height: int,
) -> None:
    """
    Main loop for sign detection process.
    Reads frames from shared buffer, runs YOLO/classifier, writes results.
    """
    import numpy as np
    import cv2
    import os
    import time
    from multiprocessing import shared_memory
    from contracts import SignType

    # Try importing ncnn and handle missing library gracefully
    try:
        import ncnn
    except ImportError:
        print("⚠️ [SignDetect] ERROR: 'ncnn' python package is not installed.")
        print("    Please run: pip install ncnn")
        # Keep process alive so orchestrator doesn't crash
        while system_running.value:
            time.sleep(0.5)
        shm.close()
        return

    TARGET_FPS = 15
    LOOP_INTERVAL = 1.0 / TARGET_FPS

    # Attach to the shared memory block (created by main.py, written by P1)
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # Load NCNN model once at startup
    model_dir = os.path.join(os.path.dirname(__file__), "models", "yolo")
    param_path = os.path.join(model_dir, "model.ncnn.param")
    bin_path = os.path.join(model_dir, "model.ncnn.bin")

    net = ncnn.Net()
    # Optimize for Raspberry Pi
    net.opt.use_vulkan_compute = False
    net.opt.num_threads = 2  # Keep threads low to not starve other processes

    # Check if files exist to avoid silent failures
    if not os.path.exists(param_path) or not os.path.exists(bin_path):
        print(f"[SignDetect] ERROR: Model files not found in {model_dir}")
        system_running.value = False
        shm.close()
        return

    net.load_param(param_path)
    net.load_model(bin_path)

    # YOLO mapping: 0 -> LEFT, 1 -> RIGHT, 2 -> STOP
    class_to_signtype = {
        0: SignType.LEFT,
        1: SignType.RIGHT,
        2: SignType.STOP
    }

    try:
        while system_running.value:
            loop_start = time.monotonic()

            # Snapshot the latest frame (~0.5ms zero-copy read)
            with frame_lock:
                frame = shared_frame.copy()

            # Preprocess frame for NCNN. We use PIXEL_BGR because the model was
            # accidentally trained on BGR images (swapped colors) due to how the
            # dataset was collected. This ensures the model sees the expected colors.
            mat_in = ncnn.Mat.from_pixels_resize(
                frame, 
                ncnn.Mat.PixelType.PIXEL_BGR, 
                frame.shape[1], 
                frame.shape[0], 
                320,  # Highly recommend 320x320 on Pi 4 for 15+ FPS
                320
            )
            
            # Normalize: divide by 255
            mean_vals = [0.0, 0.0, 0.0]
            norm_vals = [1/255.0, 1/255.0, 1/255.0]
            mat_in.substract_mean_normalize(mean_vals, norm_vals)

            # Run inference
            ex = net.create_extractor()
            ex.input("in0", mat_in)
            ret, mat_out = ex.extract("out0")

            # Post-process
            if ret == 0 and mat_out:
                # Squeeze to drop singleton batch dimensions (e.g. [1, 7, 8400] -> [7, 8400])
                out_np = np.squeeze(np.array(mat_out))
                
                # Handle flat arrays
                if len(out_np.shape) == 1:
                    num_features = 7
                    num_anchors = out_np.shape[0] // num_features
                    out_np = out_np.reshape(num_anchors, num_features)
                # Handle transposed outputs (ensure we are [anchors, features])
                elif out_np.shape[0] == 7 and len(out_np.shape) == 2:
                    out_np = out_np.T

                # Verify shape is valid before indexing
                if len(out_np.shape) == 2 and out_np.shape[1] >= 7:
                    # The last 3 columns are class scores
                    scores = out_np[:, 4:]
                    
                    # Find the max score for each class per anchor
                    max_scores_per_anchor = np.max(scores, axis=1)
                    class_ids_per_anchor = np.argmax(scores, axis=1)
                    
                    # Find the absolute best anchor
                    best_anchor_idx = np.argmax(max_scores_per_anchor)
                    best_conf = float(max_scores_per_anchor[best_anchor_idx])
                    best_class = int(class_ids_per_anchor[best_anchor_idx])

                    if best_conf >= 0.5:
                        sign_id.value = class_to_signtype.get(best_class, SignType.NONE)
                        sign_confidence.value = best_conf
                    else:
                        sign_id.value = SignType.NONE
                        sign_confidence.value = 0.0
                else:
                    sign_id.value = SignType.NONE
                    sign_confidence.value = 0.0
            else:
                sign_id.value = SignType.NONE
                sign_confidence.value = 0.0

            # Cap frame rate to prevent CPU spinning
            elapsed = time.monotonic() - loop_start
            sleep_time = LOOP_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    finally:
        shm.close()  # Always detach on exit

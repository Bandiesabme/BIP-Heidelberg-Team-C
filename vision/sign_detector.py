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
    from multiprocessing import shared_memory

    # Attach to the shared memory block (created by main.py, written by P1)
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # TODO: Load model ONCE at startup
    # from ultralytics import YOLO
    # model = YOLO("best_ncnn_model", task="detect")

    while system_running.value:
        # Snapshot the latest frame (~0.5ms zero-copy read)
        with frame_lock:
            frame = shared_frame.copy()

        # --- YOUR inference here ---
        # TODO: Run sign detection and write results:
        #   results = model.predict(frame, imgsz=320, conf=0.5)
        #
        #   if results and len(results[0].boxes) > 0:
        #       best = results[0].boxes[0]
        #       sign_id.value = int(best.cls)
        #       sign_confidence.value = float(best.conf)
        #   else:
        #       sign_id.value = SignType.NONE
        #       sign_confidence.value = 0.0

    shm.close()  # Detach from shared memory (main.py owns unlink)

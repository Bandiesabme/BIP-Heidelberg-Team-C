"""
vision/lane_detector.py — Process 1: Camera + OpenCV Lane Detection.

Runs on Core 0. Captures camera frames, detects lane markings,
and writes lane_offset / lane_curvature / lane_detected to shared memory.

Target rate: ~30 FPS.
"""

from multiprocessing import Value, Lock


def lane_detection_process(
    lane_offset: Value,       # c_double — write
    lane_curvature: Value,    # c_double — write
    lane_detected: Value,     # c_bool — write
    system_running: Value,    # c_bool — read (kill switch)
    shm_name: str,            # SharedMemory name for frame sharing with P2
    frame_lock: Lock,         # synchronize frame buffer access
    frame_width: int,
    frame_height: int,
) -> None:
    """
    Main loop for the lane detection process.
    Captures camera frames, runs OpenCV pipeline, writes results to shared memory.
    """
    import cv2
    import numpy as np
    from multiprocessing import shared_memory

    # Attach to the shared memory block created by main.py
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # Use Picamera2 to grab frames on this OS
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (frame_width, frame_height)}
        ))
        picam2.start()
    except Exception as e:
        print(f"❌ Failed to initialize Picamera2: {e}")
        return

    while system_running.value:
        try:
            # capture_array returns RGB. Convert to BGR for OpenCV
            frame_rgb = picam2.capture_array()
            frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            continue

        # Share frame with P2 via SharedMemory (~0.5ms zero-copy)
        with frame_lock:
            np.copyto(shared_frame, frame)

        # --- YOUR OpenCV pipeline here ---
        # TODO: Implement lane detection:
        #   1. Crop to bottom half (ROI)
        #   2. Convert to grayscale or HSV
        #   3. Gaussian blur (5×5)
        #   4. Canny edge detection (thresholds: 50–150)
        #   5. Hough line transform (HoughLinesP)
        #   6. Classify left/right lane lines by slope
        #      (negative slope = left lane, positive slope = right lane)
        #   7. Calculate lane center = midpoint of left and right lane
        #   8. lane_offset = image_center_x - lane_center_x
        #      (negative = car is left of center, positive = right)
        #   9. Estimate lane_curvature from slope difference
        #
        # offset, curvature, detected = run_pipeline(frame)

        # Write results atomically
        # lane_offset.value = offset
        # lane_curvature.value = curvature
        # lane_detected.value = detected

    picam2.stop()
    shm.close()  # Detach from shared memory (main.py owns unlink)

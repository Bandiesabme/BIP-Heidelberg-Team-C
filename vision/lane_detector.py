"""
vision/lane_detector.py — Process 1: Camera + OpenCV Lane Detection.

Runs on Core 0. Captures camera frames, detects lane markings,
and writes lane_offset / lane_curvature / lane_detected to shared memory.

Target rate: ~30 FPS.
"""

from multiprocessing import Value, Lock


def lane_detection_process(
    lane_offset, lane_curvature, lane_detected, system_running,
    shm_name, frame_lock, frame_width, frame_height
) -> None:
    import cv2
    import numpy as np
    from multiprocessing import shared_memory
    
    # Import the modern PiCamera2 library
    # pyrefly: ignore [missing-import]
    from picamera2 import Picamera2

    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # Initialize Picamera2
    picam2 = Picamera2()
    
    # Configure the camera to output BGR (what OpenCV and your YOLO model expect)
    # at the requested resolution
    config = picam2.create_video_configuration(
        main={"format": "BGR888", "size": (frame_width, frame_height)}
    )
    picam2.configure(config)
    picam2.start()

    while system_running.value:
        # Grab the latest frame directly as a numpy array
        try:
            frame = picam2.capture_array("main", format="bgr888")
        except Exception:
            continue

        with frame_lock:
            np.copyto(shared_frame, frame)

        # --- YOUR OpenCV pipeline here ---
        
    picam2.stop()
    shm.close()

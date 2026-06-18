"""
vision/sign_detector.py — Process 2: Lightweight NCNN Sign Detection.

Runs on Core 1. Skips frames to save CPU, enforces confidence and distance 
(bounding box area) thresholds, and debounces detections before alerting 
the Orchestrator. 

Target rate: ~10 FPS (by processing every 3rd frame of a 30 FPS stream).
"""

import time
import numpy as np
from multiprocessing import shared_memory, Value, Lock
import ncnn

# Absolute path fallback to ensure the worker always finds the contracts
import sys
import os
    
# Build absolute paths dynamically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
param_path = os.path.join(BASE_DIR, "vision", "models", "model.ncnn.param")
bin_path = os.path.join(BASE_DIR, "vision", "models", "model.ncnn.bin")
    
# Load using the absolute paths
net.load_param(param_path)
net.load_model(bin_path)
from contracts import SignType


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
    Main loop for the sign detection worker.
    """
    print("[P2-SignDetect] Initializing NCNN model...")

    # 1. Initialize NCNN Network ONCE
    net = ncnn.Net()
    # Optional: Enable Vulkan compute if supported, though CPU is fine for NCNN
    net.opt.use_vulkan_compute = False 
    
    # Load the exported weights from the YOLO training
    # Ensure these paths align with where you run main.py
    net.load_param("models/yolo/best_ncnn_model/model.param")
    net.load_model("models/yolo/best_ncnn_model/model.bin")

    # 2. Attach to the shared memory block written by P1
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # 3. Tuning Parameters (From README)
    CONF_THRESH = 0.60
    MIN_BBOX_AREA = 4000     # Minimum px area to be considered "close enough"
    REQ_CONSECUTIVE = 2      # Debounce: Must see identical sign N times in a row
    
    # State tracking variables
    frame_counter = 0
    consecutive_hits = 0
    last_seen_sign = SignType.NONE

    print("[P2-SignDetect] Online and waiting for frames.")

    while system_running.value:
        # Sleep slightly to yield CPU and prevent runaway looping
        time.sleep(0.01)
        frame_counter += 1

        # SKIPPING STRATEGY: Process 1 out of every 3 frames (~10 FPS)
        if frame_counter % 3 != 0:
            continue

        # Zero-copy frame grab
        with frame_lock:
            # We copy to avoid holding the lock during inference
            frame = shared_frame.copy() 

        # If frame is pitch black, P1 hasn't written to it yet
        if not frame.any():
            continue

        # --- PREPARE IMAGE FOR NCNN ---
        # YOLO models typically expect 320x320 or 640x640 RGB inputs.
        # Check your get_data.py / export.py for the exact imgsz you used.
        target_size = 320 
        
        # Convert numpy array to ncnn Mat, resizing and handling BGR -> RGB
        in_mat = ncnn.Mat.from_pixels_resize(
            frame,
            ncnn.Mat.PixelType.PIXEL_BGR2RGB,
            frame.shape[1],
            frame.shape[0],
            target_size,
            target_size,
        )

        # Normalize pixel values to 0.0 - 1.0 (Standard YOLO behavior)
        mean_vals = []
        norm_vals = [1 / 255.0, 1 / 255.0, 1 / 255.0]
        in_mat.substract_mean_normalize(mean_vals, norm_vals)

        # --- RUN INFERENCE ---
        ex = net.create_extractor()
        ex.input("in0", in_mat)  # "in0" is standard for YOLO NCNN exports
        
        # Extract the output tensor ("out0" is standard, check your model.param if it fails)
        ret, out_mat = ex.extract("out0") 
        
        if ret != 0 or out_mat is None:
            continue

        # --- PARSE RESULTS ---
        best_conf = 0.0
        best_label_id = -1
        best_area = 0.0

        # Iterate through detected objects (rows in the output matrix)
        for i in range(out_mat.h):
            values = out_mat.row(i)
            # Standard YOLOv8 NCNN output format per row:
            # [label, prob, x1, y1, x2, y2]
            label_id = int(values[0])
            prob = values[1]
            x1, y1, x2, y2 = values[2], values[3], values[4], values[5]
            
            # Calculate actual area scaled back to original frame size
            w = (x2 - x1) * frame_width
            h = (y2 - y1) * frame_height
            area = w * h

            if prob > best_conf:
                best_conf = prob
                best_label_id = label_id
                best_area = area

        # --- EVALUATE THRESHOLDS & DEBOUNCE ---
        current_detected_sign = SignType.NONE

        if best_conf >= CONF_THRESH and best_area >= MIN_BBOX_AREA:
            # Map the raw model class IDs (0, 1, 2) to your SignType Enum.
            # IMPORTANT: Ensure this mapping matches your Roboflow dataset labels!
            if best_label_id == 0:   # Example: 0 = Left in dataset
                current_detected_sign = SignType.LEFT
            elif best_label_id == 1: # Example: 1 = Right in dataset
                current_detected_sign = SignType.RIGHT
            elif best_label_id == 2: # Example: 2 = Stop in dataset
                current_detected_sign = SignType.STOP

        # Debounce Logic: Ensure we see the *same* sign multiple frames in a row
        if current_detected_sign != SignType.NONE and current_detected_sign == last_seen_sign:
            consecutive_hits += 1
        else:
            consecutive_hits = 1
            last_seen_sign = current_detected_sign

        # If it passes the debounce threshold, write it to shared memory
        if consecutive_hits >= REQ_CONSECUTIVE and current_detected_sign != SignType.NONE:
            sign_id.value = current_detected_sign
            sign_confidence.value = float(best_conf)
            # Reset hits so we don't spam the Orchestrator with the same event
            consecutive_hits = 0 

    # Cleanup when system terminates
    shm.close()
    print("[P2-SignDetect] Shutdown complete.")
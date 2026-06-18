"""
Stop-sign detection using the trained YOLOv8n model.

We do NOT run this every frame (inference is ~0.5s on the Pi). The main loop
calls detect() every Nth frame on a frame it already captured. Lane following
keeps running every frame in between.

Distance is judged by detection box SIZE: a close sign fills more of the frame.
We report the biggest stop-sign box height as a fraction of frame height
(0..1). The caller decides the trigger threshold (tunable live).
"""

import time


class SignDetector:
    def __init__(self, model_path="best.pt", conf=0.45, stop_class_id=2):
        # class ids from the model: 0 left-sign, 1 right-sign, 2 stop-sign
        self.stop_class_id = stop_class_id
        self.conf = conf
        self.model = None
        self._load_error = None
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            print(f"[Signs] YOLO model loaded from {model_path}")
        except Exception as e:
            self._load_error = str(e)
            print(f"[Signs] Could not load YOLO model ({e}). Sign detection disabled.")

    def detect_signs(self, frame_bgr):
        """
        Run inference and return (sign_name, size_fraction, conf).
        sign_name is one of 'left', 'right', 'stop', or None.
        size_fraction = height of the biggest sign box / frame height (0..1).
        If no sign: (None, 0.0, 0.0).
        """
        if self.model is None:
            return (None, 0.0, 0.0)

        frame_h = frame_bgr.shape[0]
        try:
            results = self.model(frame_bgr, conf=self.conf, verbose=False)
        except Exception as e:
            print(f"[Signs] inference error: {e}")
            return (None, 0.0, 0.0)

        best_frac = 0.0
        best_conf = 0.0
        best_sign = None
        
        # map class ids to names based on comment: 0 left-sign, 1 right-sign, 2 stop-sign
        class_names = {0: 'left', 1: 'right', 2: 'stop'}

        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                cls = int(b.cls[0])
                if cls not in class_names:
                    continue
                conf = float(b.conf[0])
                # xyxy box -> height in pixels
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                box_h = abs(y2 - y1)
                frac = box_h / float(frame_h)
                if frac > best_frac:
                    best_frac = frac
                    best_conf = conf
                    best_sign = class_names[cls]

        return (best_sign, best_frac, best_conf)
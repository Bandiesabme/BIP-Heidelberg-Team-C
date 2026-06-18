import cv2
import numpy as np

class SignDetector:
    def __init__(self):
        # Default HSV settings (tunable via web server)
        self.blue_h_min = 100
        self.blue_h_max = 140
        self.sign_s_min = 120
        self.sign_v_min = 70
        print("[Signs] Lightweight CV Sign Detector Initialized.")

    def detect_signs(self, frame_bgr):
        """
        Returns (sign_name, size_fraction, conf)
        Conf is always 1.0 for this simple logic.
        """
        frame_h = frame_bgr.shape[0]
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        
        # Red ranges (Wraps around the 0/180 mark in OpenCV)
        lower_red1 = np.array([0, self.sign_s_min, self.sign_v_min])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, self.sign_s_min, self.sign_v_min])
        upper_red2 = np.array([180, 255, 255])
        
        # Blue range
        lower_blue = np.array([self.blue_h_min, self.sign_s_min, self.sign_v_min])
        upper_blue = np.array([self.blue_h_max, 255, 255])
        
        mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        best_sign = None
        best_frac = 0.0
        
        # 1. Check for Red (Stop)
        contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours_red:
            largest_red = max(contours_red, key=cv2.contourArea)
            if cv2.contourArea(largest_red) > 500:
                _, y, _, h = cv2.boundingRect(largest_red)
                best_frac = h / float(frame_h)
                best_sign = "stop"
                
        # 2. Check for Blue (Turn Signs)
        contours_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours_blue:
            largest_blue = max(contours_blue, key=cv2.contourArea)
            if cv2.contourArea(largest_blue) > 500:
                x, y, w, h = cv2.boundingRect(largest_blue)
                frac = h / float(frame_h)
                
                # If the blue sign is closer than the red sign, overwrite it
                if frac > best_frac:
                    best_frac = frac
                    
                    # Arrow detection logic (count white pixels on left vs right)
                    sign_roi = frame_bgr[y:y+h, x:x+w]
                    gray = cv2.cvtColor(sign_roi, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
                    
                    midpoint = w // 2
                    left_white = cv2.countNonZero(thresh[:, :midpoint])
                    right_white = cv2.countNonZero(thresh[:, midpoint:])
                    
                    best_sign = "left" if left_white > right_white else "right"

        return (best_sign, best_frac, 1.0)
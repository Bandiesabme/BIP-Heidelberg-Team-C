import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import cv2

# Import local LaneDetector & Autodrive Controller
from lane_decetion import LaneDetector
import autodrive
from sign_detection import SignDetector

# Thread-safe global stores
latest_raw_frame = None
latest_processed_frame = None
frame_lock = threading.Lock()

# Telemetry variables (readings only)
last_lane_found = False
last_steering_error = 0.0

# Sign detection settings/telemetry
sign_check_every = 4          # run YOLO every Nth frame (inference is slow)
sign_trigger_frac = 0.35      # sign box height >= this fraction of frame -> ACTION. tunable live
last_sign_frac = 0.0          # most recent detected sign size (telemetry)
last_sign_seen = None         # None, 'stop', 'left', 'right'

detector = LaneDetector()
sign_detector = SignDetector(model_path="best.pt")

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded server to handle concurrent image requests without blocking."""
    daemon_threads = True
    allow_reuse_address = True

class SimpleWebStreamer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging console spam
        return

    def do_GET(self):
        global latest_raw_frame, latest_processed_frame
        global last_lane_found, last_steering_error
        global sign_trigger_frac
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        if path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            try:
                # Load HTML from file dynamically
                html_path = os.path.join(os.path.dirname(__file__), 'index.html')
                with open(html_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                self.wfile.write(f"<h1>Error loading index.html</h1><p>{e}</p>".encode('utf-8'))
            
        elif path == '/camera.mjpg':
            self.send_response(200)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        if latest_raw_frame is None:
                            jpeg_bytes = None
                        else:
                            _, jpeg_buf = cv2.imencode('.jpg', latest_raw_frame)
                            jpeg_bytes = jpeg_buf.tobytes()
                    
                    if jpeg_bytes is not None:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(jpeg_bytes)))
                        self.end_headers()
                        self.wfile.write(jpeg_bytes)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.05)  # Stream at ~20 FPS for efficiency
            except Exception:
                pass

        elif path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        if latest_processed_frame is None:
                            jpeg_bytes = None
                        else:
                            _, jpeg_buf = cv2.imencode('.jpg', latest_processed_frame)
                            jpeg_bytes = jpeg_buf.tobytes()
                    
                    if jpeg_bytes is not None:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(jpeg_bytes)))
                        self.end_headers()
                        self.wfile.write(jpeg_bytes)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.05)
            except Exception:
                pass
                
        elif path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            import json
            status_data = {
                "autodrive_enabled": autodrive.autodrive_enabled,
                "lane_found": last_lane_found,
                "steering_error": last_steering_error,
                "motor_speed": autodrive.current_speed,
                "steering_angle": autodrive.current_angle,
                "white_thresh": detector.white_thresh,
                "roi_top_ratio": detector.roi_top_ratio,
                "follow_offset": detector.follow_offset,
                "stop_trigger_frac": sign_trigger_frac,
                "stop_size": last_sign_frac,
                "stopped": autodrive._stopped_for_sign,
                "target_speed": autodrive.target_speed,
                "max_steering_angle": autodrive.max_steering_angle,
                "camera_pan": autodrive.camera_pan,
                "camera_tilt": autodrive.camera_tilt
                "last_sign": last_sign_seen,          # 
                "turn_frames": autodrive.turn_frames  # 
            }
            self.wfile.write(json.dumps(status_data).encode('utf-8'))
            
        elif path == '/api/set':
            if 'autodrive' in query:
                autodrive.set_autodrive(query['autodrive'][0] == '1')
            if 'speed' in query:
                autodrive.set_speed(int(query['speed'][0]))
            if 'max_angle' in query:
                autodrive.set_max_angle(int(query['max_angle'][0]))
            if 'white_thresh' in query:
                detector.white_thresh = int(query['white_thresh'][0])
            if 'roi_top_ratio' in query:
                detector.roi_top_ratio = float(query['roi_top_ratio'][0])
            if 'follow_offset' in query:
                detector.follow_offset = float(query['follow_offset'][0])
            if 'stop_trigger' in query:
                sign_trigger_frac = float(query['stop_trigger'][0])
            if 'cam_pan' in query:
                autodrive.set_pan(int(query['cam_pan'][0]))
            if 'cam_tilt' in query:
                autodrive.set_tilt(int(query['cam_tilt'][0]))
            if 'cam_tilt' in query:
                autodrive.set_tilt(int(query['cam_tilt'][0]))
            if 'turn_frames' in query:                                   
                autodrive.set_turn_frames(int(query['turn_frames'][0]))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

def capture_thread():
    global latest_raw_frame, latest_processed_frame
    global last_lane_found, last_steering_error
    global last_sign_frac, last_sign_seen, sign_trigger_frac

    frame_count = 0
    
    # Try Picamera2 (Raspberry Pi native), fall back to OpenCV VideoCapture (Windows/USB webcam)
    cap = None
    picam2 = None
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (640, 480)}
        ))
        picam2.start()
        print("[Camera] Picamera2 started.")
    except Exception:
        print("[Camera] Picamera2 not found. Falling back to OpenCV...")
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Initialize Autodrive controller client
    autodrive.init_picarx()

    while True:
        if picam2:
            try:
                frame = picam2.capture_array()
            except Exception:
                time.sleep(0.01)
                continue
        else:
            if cap and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
            else:
                time.sleep(0.1)
                continue
                
        # Perform lane detection
        result = detector.detect(frame)
        
        last_lane_found = result.lane_found
        last_steering_error = result.steering_error

        # Sign detection: only every Nth frame (inference is ~0.5s on the Pi).
        # Runs regardless of autodrive state so you can bench-test the readout.
        # The actual STOP action only fires while autodrive is enabled.
        frame_count += 1
        if frame_count % sign_check_every == 0:
            sign_name, sign_frac, sign_conf = sign_detector.detect_signs(frame)
            last_sign_seen = sign_name
            last_sign_frac = sign_frac
            # Trigger action only when close enough AND actually driving
            if sign_name is not None and sign_frac >= sign_trigger_frac and autodrive.autodrive_enabled:
                if sign_name == 'stop':
                    print(f"[Signs] STOP sign close (size {sign_frac:.2f} >= {sign_trigger_frac:.2f}). Stopping.")
                    autodrive.trigger_stop()
                elif sign_name == 'left':
                    print(f"[Signs] LEFT turn sign close. Turning left.")
                    autodrive.trigger_turn('left')
                elif sign_name == 'right':
                    print(f"[Signs] RIGHT turn sign close. Turning right.")
                    autodrive.trigger_turn('right')
        
        raw_frame = frame.copy()
        processed = result.debug_image if result.debug_image is not None else frame.copy()
        
        # Overlay visual stats on the processed video feed
        status_text = f"Offset: {result.steering_error:.2f} | Lane: {'Locked' if result.lane_found else 'Lost'}"
        color = (0, 255, 0) if result.lane_found else (0, 0, 255)
        cv2.putText(processed, status_text, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        # Show sign size so you can tune the trigger live
        sign_text = f"Sign size: {last_sign_frac:.2f} (trigger {sign_trigger_frac:.2f})"
        if last_sign_seen:
            sign_text = f"{last_sign_seen.upper()} " + sign_text
        sign_color = (0, 0, 255) if last_sign_frac >= sign_trigger_frac else (255, 255, 0)
        cv2.putText(processed, sign_text, (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, sign_color, 2, cv2.LINE_AA)
        
        with frame_lock:
            latest_raw_frame = raw_frame
            latest_processed_frame = processed
            
        # Drive robot using the separated autodrive controller
        autodrive.update(result.lane_found, result.steering_error)
            
        time.sleep(0.033)

if __name__ == '__main__':
    # Start background capture thread
    t = threading.Thread(target=capture_thread, daemon=True)
    t.start()
    
    # Run HTTP Server
    port = 5001
    server = ThreadingHTTPServer(('0.0.0.0', port), SimpleWebStreamer)
    print(f"🚀 Autodrive Web Server started at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
import os
import time
import threading
import cv2
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse

# Import local modules
from lane_decetion import LaneDetector
import autodrive
from sign_detection import SignDetector

# Thread-safe global stores (Now storing raw bytes, not CV2 arrays!)
latest_raw_jpg = None
latest_processed_jpg = None
frame_lock = threading.Lock()

# Telemetry variables
last_lane_found = False
last_steering_error = 0.0

# Sign detection settings/telemetry
sign_check_every = 4
sign_trigger_frac = 0.35
last_sign_frac = 0.0
last_sign_seen = None

# Initialize detectors
detector = LaneDetector()
sign_detector = SignDetector()

# Initialize FastAPI
app = FastAPI()

# --- STATIC FILES ROUTING ---
@app.get("/")
async def get_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

@app.get("/style.css")
async def get_css():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'style.css'))

@app.get("/script.js")
async def get_js():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'script.js'))

# --- VIDEO STREAM GENERATORS ---
def generate_raw_frames():
    while True:
        with frame_lock:
            jpeg_bytes = latest_raw_jpg
        if jpeg_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n\r\n' + 
                   jpeg_bytes + b'\r\n')
        time.sleep(0.033)  # Limits the web stream to ~30fps

def generate_processed_frames():
    while True:
        with frame_lock:
            jpeg_bytes = latest_processed_jpg
        if jpeg_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n\r\n' + 
                   jpeg_bytes + b'\r\n')
        time.sleep(0.033)

@app.get("/camera.mjpg")
async def raw_feed():
    return StreamingResponse(generate_raw_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/stream.mjpg")
async def processed_feed():
    return StreamingResponse(generate_processed_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# --- API ROUTING ---
@app.get("/api/status")
async def get_status():
    return {
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
        "camera_tilt": autodrive.camera_tilt,
        "last_sign": last_sign_seen,
        "turn_frames": autodrive.turn_frames,
        "blue_h_min": sign_detector.blue_h_min,
        "blue_h_max": sign_detector.blue_h_max,
        "sign_s_min": sign_detector.sign_s_min,
        "sign_v_min": sign_detector.sign_v_min
    }

@app.get("/api/set")
async def set_params(request: Request):
    global sign_trigger_frac
    query = request.query_params
    
    if 'autodrive' in query:
        autodrive.set_autodrive(query['autodrive'] == '1')
    if 'speed' in query:
        autodrive.set_speed(int(query['speed']))
    if 'max_angle' in query:
        autodrive.set_max_angle(int(query['max_angle']))
    if 'white_thresh' in query:
        detector.white_thresh = int(query['white_thresh'])
    if 'roi_top_ratio' in query:
        detector.roi_top_ratio = float(query['roi_top_ratio'])
    if 'follow_offset' in query:
        detector.follow_offset = float(query['follow_offset'])
    if 'stop_trigger' in query:
        sign_trigger_frac = float(query['stop_trigger'])
    if 'cam_pan' in query:
        autodrive.set_pan(int(query['cam_pan']))
    if 'cam_tilt' in query:
        autodrive.set_tilt(int(query['cam_tilt']))
    if 'turn_frames' in query:
        autodrive.set_turn_frames(int(query['turn_frames']))
    if 'blue_h_min' in query:
        sign_detector.blue_h_min = int(query['blue_h_min'])
    if 'blue_h_max' in query:
        sign_detector.blue_h_max = int(query['blue_h_max'])
    if 'sign_s_min' in query:
        sign_detector.sign_s_min = int(query['sign_s_min'])
    if 'sign_v_min' in query:
        sign_detector.sign_v_min = int(query['sign_v_min'])
        
    return {"status": "ok"}


def capture_thread():
    global latest_raw_jpg, latest_processed_jpg
    global last_lane_found, last_steering_error
    global last_sign_frac, last_sign_seen, sign_trigger_frac

    frame_count = 0
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
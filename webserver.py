"""
web_server.py — Process 5: Flask Monitoring Dashboard.

Runs on its own core. Reads camera frames from shared memory
and motor states from mp.Values.
"""
import time
import cv2
import numpy as np
from multiprocessing import shared_memory
from flask import Flask, Response, jsonify

app = Flask(__name__)

# Global references to shared memory (injected on process start)
_shm_name = None
_frame_lock = None
_frame_w = 0
_frame_h = 0
_speed = None
_steering = None

def generate_video_feed():
    """Generator yielding JPEG frames for the MJPEG stream."""
    shm = shared_memory.SharedMemory(name=_shm_name)
    shared_frame = np.ndarray(
        (_frame_h, _frame_w, 3), dtype=np.uint8, buffer=shm.buf
    )

    while True:
        # Atomic read of the latest frame
        with _frame_lock:
            frame = shared_frame.copy()
            
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03)  # Roughly 30 FPS cap

@app.route('/')
def index():
    """Simple HTML dashboard dashboard."""
    return """
    <html>
        <head>
            <title>PiCar-X Telemetry</title>
            <style>
                body { font-family: sans-serif; background: #121212; color: #fff; text-align: center; }
                img { max-width: 100%; border: 2px solid #333; border-radius: 8px; }
                .telemetry { margin-top: 20px; font-size: 1.5em; }
            </style>
        </head>
        <body>
            <h1>PiCar-X Live View</h1>
            <img src="/video_feed" />
            <div class="telemetry">
                <p>Speed: <span id="speed">0</span></p>
                <p>Steering: <span id="steering">0</span>&deg;</p>
            </div>
            <script>
                setInterval(() => {
                    fetch('/api/telemetry')
                        .then(r => r.json())
                        .then(data => {
                            document.getElementById('speed').innerText = data.speed.toFixed(1);
                            document.getElementById('steering').innerText = data.steering.toFixed(1);
                        });
                }, 100); // Poll telemetry at 10Hz
            </script>
        </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_video_feed(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/telemetry')
def telemetry():
    return jsonify({
        "speed": _speed.value,
        "steering": _steering.value
    })

def web_server_process(
    speed_val, steering_val, shm_name, frame_lock, frame_w, frame_h
):
    """Entry point for Process 5."""
    global _shm_name, _frame_lock, _frame_w, _frame_h, _speed, _steering
    _shm_name = shm_name
    _frame_lock = frame_lock
    _frame_w = frame_w
    _frame_h = frame_h
    _speed = speed_val
    _steering = steering_val
    
    # Run Flask securely on all interfaces (0.0.0.0) at port 5000
    # use_reloader=False is MANDATORY when running inside a multiprocessing Process
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
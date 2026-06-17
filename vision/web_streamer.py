"""
vision/web_streamer.py — Live Web Streamer & Telemetry Dashboard for PiCar-X.

Provides a live web server using Python's built-in http.server (no external
dependencies like Flask required). Supports:
1. Standalone Mode: Run `python vision/web_streamer.py` to test sign detection
   at your desk with direct camera capture and NCNN inference.
2. Integrated Mode: Can be spawned as a process in main.py to stream live video
   and telemetry from shared memory while the car is running.
"""

import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cv2
import numpy as np

# Global state dictionary for sharing between camera/inference and web server threads
state = {
    "latest_frame_jpeg": None,
    "fps": 0.0,
    "latency_ms": 0.0,
    "detected_class": "NONE",
    "confidence": 0.0,
    "threshold": 0.5,
    "lane_offset": 0.0,
    "lane_curvature": 0.0,
    "lane_detected": False,
    "obstacle_dist": 999.0,
    "voice_command": "NONE",
    "running": True
}

# Lock for protecting state writes/reads
state_lock = threading.Lock()

# YOLO class mapping
CLASS_NAMES = {0: "LEFT", 1: "RIGHT", 2: "STOP"}

# Beautiful, premium dashboard HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PiCar-X Live Vision & Telemetry</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --panel-bg: rgba(17, 24, 39, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(239, 68, 68, 0.1) 0px, transparent 50%);
        }

        header {
            width: 100%;
            max-width: 1200px;
            padding: 2rem 1.5rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo-area h1 {
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #3b82f6, #60a5fa, #ef4444);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-area p {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 2px;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent-green);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        .container {
            width: 100%;
            max-width: 1200px;
            padding: 1rem 1.5rem 3rem;
            display: grid;
            grid-template-columns: 1.6fr 1fr;
            gap: 1.5rem;
        }

        @media (max-width: 900px) {
            .container {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        .video-panel {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
            min-height: 480px;
        }

        .video-feed {
            width: 100%;
            max-width: 640px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            background-color: #000;
        }

        .control-panel {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .panel-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .stat-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 1.6rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        .detection-card {
            grid-column: span 2;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.25rem;
            border-radius: 12px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .detection-card.NONE {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .detection-card.LEFT {
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.15);
        }

        .detection-card.RIGHT {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.15);
        }

        .detection-card.STOP {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.15);
        }

        .detection-name {
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: 0.5px;
        }

        .detection-conf {
            font-size: 1.1rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }

        .slider-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 0.5rem;
        }

        .slider-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        input[type="range"] {
            -webkit-appearance: none;
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            outline: none;
        }

        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--accent-blue);
            cursor: pointer;
            transition: transform 0.1s;
        }

        input[type="range"]::-webkit-slider-thumb:hover {
            transform: scale(1.2);
        }

        .telemetry-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }

        .telemetry-row:last-child {
            border-bottom: none;
        }

        .telemetry-label {
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        .telemetry-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 0.95rem;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-area">
            <h1>PiCar-X Live Vision</h1>
            <p>Team C — Sign Detection & Telemetry</p>
        </div>
        <div class="status-pill">
            <div class="status-dot"></div>
            <span>LIVE SERVER</span>
        </div>
    </header>

    <div class="container">
        <div class="panel video-panel">
            <div class="panel-title" style="align-self: flex-start; width: 100%;">
                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                Camera Viewport
            </div>
            <img class="video-feed" src="/stream.mjpg" alt="Video Stream">
        </div>

        <div class="control-panel">
            <div class="panel">
                <div class="panel-title">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z"/></svg>
                    Detections
                </div>
                <div class="stats-grid">
                    <div id="detection-box" class="detection-card NONE">
                        <div>
                            <div class="stat-label">Detected Sign</div>
                            <div id="det-class" class="detection-name">NONE</div>
                        </div>
                        <div id="det-conf" class="detection-conf">0.0%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Inference Time</div>
                        <div id="stat-latency" class="stat-value">0.0 ms</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Vision FPS</div>
                        <div id="stat-fps" class="stat-value">0.0</div>
                    </div>
                </div>

                <div class="slider-container" style="margin-top: 1.5rem;">
                    <div class="slider-header">
                        <span>Confidence Threshold</span>
                        <span id="threshold-val">0.50</span>
                    </div>
                    <input type="range" id="threshold-slider" min="0.1" max="0.95" step="0.05" value="0.50" oninput="updateThreshold(this.value)">
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                    Car Telemetry
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Lane Detection Status</span>
                    <span id="tel-lane-det" class="telemetry-value" style="color: var(--accent-red);">NOT DETECTED</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Lane Offset</span>
                    <span id="tel-offset" class="telemetry-value">0.0 px</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Lane Curvature</span>
                    <span id="tel-curvature" class="telemetry-value">0.00</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Obstacle Distance</span>
                    <span id="tel-obstacle" class="telemetry-value">999.0 cm</span>
                </div>
                <div class="telemetry-row">
                    <span class="telemetry-label">Voice Command</span>
                    <span id="tel-voice" class="telemetry-value" style="color: var(--accent-blue);">NONE</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        function updateStats() {
            fetch('/stats')
                .then(response => response.json())
                .then(data => {
                    // Update class and styling
                    const box = document.getElementById('detection-box');
                    box.className = `detection-card ${data.detected_class}`;
                    
                    document.getElementById('det-class').innerText = data.detected_class;
                    document.getElementById('det-conf').innerText = (data.confidence * 100).toFixed(1) + '%';
                    document.getElementById('stat-latency').innerText = data.latency_ms.toFixed(1) + ' ms';
                    document.getElementById('stat-fps').innerText = data.fps.toFixed(1);
                    
                    // Threshold slider if it wasn't adjusted by user
                    if (document.activeElement !== document.getElementById('threshold-slider')) {
                        document.getElementById('threshold-slider').value = data.threshold;
                        document.getElementById('threshold-val').innerText = data.threshold.toFixed(2);
                    }

                    // Update Telemetry
                    const laneDet = document.getElementById('tel-lane-det');
                    if (data.lane_detected) {
                        laneDet.innerText = "ACTIVE";
                        laneDet.style.color = "var(--accent-green)";
                    } else {
                        laneDet.innerText = "NOT DETECTED";
                        laneDet.style.color = "var(--accent-red)";
                    }
                    
                    document.getElementById('tel-offset').innerText = data.lane_offset.toFixed(1) + ' px';
                    document.getElementById('tel-curvature').innerText = data.lane_curvature.toFixed(4);
                    
                    const obs = document.getElementById('tel-obstacle');
                    obs.innerText = data.obstacle_dist.toFixed(1) + ' cm';
                    if (data.obstacle_dist < 30) {
                        obs.style.color = "var(--accent-red)";
                    } else if (data.obstacle_dist < 50) {
                        obs.style.color = "var(--accent-yellow)";
                    } else {
                        obs.style.color = "var(--text-main)";
                    }

                    document.getElementById('tel-voice').innerText = data.voice_command;
                })
                .catch(err => console.error("Error fetching stats:", err));
        }

        function updateThreshold(val) {
            document.getElementById('threshold-val').innerText = parseFloat(val).toFixed(2);
            fetch(`/set_threshold?val=${val}`);
        }

        // Poll stats at 5Hz (every 200ms) for high responsiveness
        setInterval(updateStats, 200);
    </script>
</body>
</html>
"""

class TelemetryHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler using standard library only."""

    def log_message(self, format, *args):
        # Suppress logging in console to avoid flooding the terminal
        return

    def do_GET(self):
        global state
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache, private')
            self.end_headers()
            with state_lock:
                stats_data = {
                    "fps": state["fps"],
                    "latency_ms": state["latency_ms"],
                    "detected_class": state["detected_class"],
                    "confidence": state["confidence"],
                    "threshold": state["threshold"],
                    "lane_offset": state["lane_offset"],
                    "lane_curvature": state["lane_curvature"],
                    "lane_detected": state["lane_detected"],
                    "obstacle_dist": state["obstacle_dist"],
                    "voice_command": state["voice_command"]
                }
            self.wfile.write(json.dumps(stats_data).encode('utf-8'))
            
        elif self.path.startswith('/set_threshold'):
            try:
                # Simple query parsing
                val_str = self.path.split('val=')[1]
                val = float(val_str)
                with state_lock:
                    state["threshold"] = val
                print(f"[WebStreamer] Confidence threshold updated to: {val:.2f}")
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            try:
                last_frame_time = 0
                while True:
                    with state_lock:
                        jpeg_bytes = state["latest_frame_jpeg"]
                        running = state["running"]
                    
                    if not running:
                        break
                        
                    if jpeg_bytes is None:
                        time.sleep(0.03)
                        continue
                        
                    # Stream frames at ~25-30 FPS maximum to conserve network bandwidth
                    now = time.monotonic()
                    if now - last_frame_time < 0.033:
                        time.sleep(0.01)
                        continue
                    last_frame_time = now

                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(jpeg_bytes)))
                    self.end_headers()
                    self.wfile.write(jpeg_bytes)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                # Connection closed by browser
                pass
        else:
            self.send_response(404)
            self.end_headers()


def draw_detection_overlay(frame, best_box, best_class, best_conf):
    """Draw a styled glassmorphic bounding box and label on the image."""
    h, w, _ = frame.shape
    
    # Automatic box format detection
    # YOLO raw coordinate format can be [x_center, y_center, width, height]
    # We support both normalized (0..1) and raw pixels (relative to 320x320)
    is_normalized = all(v <= 1.05 for v in best_box)
    scale_x = w if is_normalized else (w / 320.0)
    scale_y = h if is_normalized else (h / 320.0)
    
    # Check if format is x_center, y_center, w, h
    # If the width/height calculations would result in values out of bounds,
    # we dynamically verify.
    cx, cy, bw, bh = best_box
    
    # Check if coordinates represent corner coords x1, y1, x2, y2 instead
    # Typically, in corner coords: x2 > x1 and y2 > y1. Also, cx is x1, cy is y1.
    # In center-width format: cx can be smaller than bw, but if bw > cx * 2 it's likely corners.
    # We check if bw > cx and bh > cy and cx + bw/2 > 320 (or > 1.0) to see if corners are more likely.
    if cx < bw and cy < bh and bw <= 320.0 and bh <= 320.0 and (cx + bw/2 > 320.0):
        # Likely corner format [x1, y1, x2, y2]
        x1 = int(cx * scale_x)
        y1 = int(cy * scale_y)
        x2 = int(bw * scale_x)
        y2 = int(bh * scale_y)
    else:
        # Standard center-width-height format [x_center, y_center, w, h]
        x1 = int((cx - bw / 2) * scale_x)
        y1 = int((cy - bh / 2) * scale_y)
        x2 = int((cx + bw / 2) * scale_x)
        y2 = int((cy + bh / 2) * scale_y)
        
    # Clip coordinates to frame
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(0, min(w - 1, x2))
    y2 = max(0, min(h - 1, y2))
    
    # Colors (BGR)
    # Class 0: LEFT (Blue), Class 1: RIGHT (Green), Class 2: STOP (Red)
    colors = {
        0: (246, 130, 59),  # Blue/Orange mix
        1: (129, 185, 16),  # Green
        2: (68, 68, 239)    # Red
    }
    color = colors.get(best_class, (255, 255, 255))
    class_name = CLASS_NAMES.get(best_class, "UNKNOWN")
    
    # 1. Draw bounding box with nice double border (neon outer, dark inner)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 3)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    
    # 2. Draw stylish corner brackets for high-end feel
    bracket_len = min(20, int((x2 - x1) * 0.2))
    # Top Left
    cv2.line(frame, (x1, y1), (x1 + bracket_len, y1), color, 4)
    cv2.line(frame, (x1, y1), (x1, y1 + bracket_len), color, 4)
    # Top Right
    cv2.line(frame, (x2, y1), (x2 - bracket_len, y1), color, 4)
    cv2.line(frame, (x2, y1), (x2, y1 + bracket_len), color, 4)
    # Bottom Left
    cv2.line(frame, (x1, y2), (x1 + bracket_len, y2), color, 4)
    cv2.line(frame, (x1, y2), (x1, y2 - bracket_len), color, 4)
    # Bottom Right
    cv2.line(frame, (x2, y2), (x2 - bracket_len, y2), color, 4)
    cv2.line(frame, (x2, y2), (x2, y2 - bracket_len), color, 4)

    # 3. Label text background
    label = f"{class_name} ({best_conf*100:.1f}%)"
    (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    
    # Place label above the box if room, else inside
    label_y = y1 - 10 if y1 - 10 > label_h else y1 + label_h + 10
    
    # Label card background
    cv2.rectangle(frame, (x1, label_y - label_h - 6), (x1 + label_w + 10, label_y + baseline + 2), (0, 0, 0), -1)
    cv2.rectangle(frame, (x1, label_y - label_h - 6), (x1 + label_w + 10, label_y + baseline + 2), color, 1)
    
    # Draw text
    cv2.putText(frame, label, (x1 + 5, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def standalone_inference_loop():
    """Producer Thread: direct camera capture and optional YOLO inference."""
    global state

    print("[WebStreamer] Starting Standalone Camera & Inference loop...")
    
    # Try importing ncnn and handle missing package gracefully
    try:
        import ncnn
        has_ncnn = True
    except ImportError:
        print("⚠️ [WebStreamer] WARNING: 'ncnn' python package is not installed.")
        print("    Live streaming will still work, but sign detection overlays are disabled.")
        print("    To enable sign detection overlays, run: pip install ncnn")
        has_ncnn = False

    net = None
    if has_ncnn:
        # Load model
        model_dir = os.path.join(os.path.dirname(__file__), "models", "yolo")
        param_path = os.path.join(model_dir, "model.ncnn.param")
        bin_path = os.path.join(model_dir, "model.ncnn.bin")
        
        if not os.path.exists(param_path) or not os.path.exists(bin_path):
            print(f"[WebStreamer] WARNING: NCNN Model files not found in {model_dir}. Bypassing detection.")
            has_ncnn = False
        else:
            try:
                net = ncnn.Net()
                net.opt.use_vulkan_compute = False
                net.opt.num_threads = 2
                net.load_param(param_path)
                net.load_model(bin_path)
                print("[WebStreamer] NCNN Model loaded successfully.")
            except Exception as e:
                print(f"[WebStreamer] Failed to load NCNN network: {e}. Bypassing detection.")
                has_ncnn = False

    # Initialize Camera
    cap = None
    picam2 = None
    
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (640, 480)}
        ))
        picam2.start()
        print("[WebStreamer] Picamera2 initialized successfully.")
    except Exception as e:
        print(f"[WebStreamer] Picamera2 not available, trying OpenCV VideoCapture: {e}")
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not cap.isOpened():
            print("[WebStreamer] ERROR: Could not open any camera resource.")
            with state_lock:
                state["running"] = False
            return
            
    fps_time = time.monotonic()
    frame_counter = 0

    try:
        while True:
            with state_lock:
                running = state["running"]
                threshold = state["threshold"]
            
            if not running:
                break
                
            loop_start = time.monotonic()

            # 1. Capture Frame
            if picam2:
                try:
                    frame_rgb = picam2.capture_array()
                    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                except Exception as ex:
                    print(f"[WebStreamer] Frame capture error: {ex}")
                    continue
            else:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

            # 2. Run NCNN Inference (Only if we have ncnn and model successfully loaded)
            det_class_name = "NONE"
            det_conf = 0.0
            inf_time = 0.0

            if has_ncnn and net is not None:
                mat_in = ncnn.Mat.from_pixels_resize(
                    frame, 
                    ncnn.Mat.PixelType.PIXEL_BGR, 
                    frame.shape[1], 
                    frame.shape[0], 
                    320, 
                    320
                )
                
                # Normalize: divide by 255
                mean_vals = [0.0, 0.0, 0.0]
                norm_vals = [1/255.0, 1/255.0, 1/255.0]
                mat_in.substract_mean_normalize(mean_vals, norm_vals)

                inf_start = time.monotonic()
                ex = net.create_extractor()
                ex.input("in0", mat_in)
                ret_code, mat_out = ex.extract("out0")
                inf_time = (time.monotonic() - inf_start) * 1000.0

                # 3. Process Detections
                if ret_code == 0 and mat_out:
                    out_np = np.squeeze(np.array(mat_out))
                    
                    # Reshape if flat
                    if len(out_np.shape) == 1:
                        num_features = 7
                        num_anchors = out_np.shape[0] // num_features
                        out_np = out_np.reshape(num_anchors, num_features)
                    elif out_np.shape[0] == 7 and len(out_np.shape) == 2:
                        out_np = out_np.T

                    if len(out_np.shape) == 2 and out_np.shape[1] >= 7:
                        # Scores are columns 4 to end
                        scores = out_np[:, 4:]
                        max_scores = np.max(scores, axis=1)
                        class_ids = np.argmax(scores, axis=1)
                        
                        best_idx = np.argmax(max_scores)
                        best_conf = float(max_scores[best_idx])
                        best_class = int(class_ids[best_idx])

                        if best_conf >= threshold:
                            det_class_name = CLASS_NAMES.get(best_class, "UNKNOWN")
                            det_conf = best_conf
                            best_box = out_np[best_idx, :4]
                            draw_detection_overlay(frame, best_box, best_class, best_conf)

            # 4. Measure FPS
            frame_counter += 1
            now = time.monotonic()
            elapsed_fps = now - fps_time
            current_fps = state["fps"]
            if elapsed_fps >= 1.0:
                current_fps = frame_counter / elapsed_fps
                frame_counter = 0
                fps_time = now

            # 5. Compress to JPEG
            _, jpeg_buffer = cv2.imencode('.jpg', frame)
            jpeg_bytes = jpeg_buffer.tobytes()

            # 6. Update Shared Web Server State
            with state_lock:
                state["latest_frame_jpeg"] = jpeg_bytes
                state["fps"] = current_fps
                state["latency_ms"] = inf_time
                state["detected_class"] = det_class_name
                state["confidence"] = det_conf

            # Cap frame rate to ~30 FPS to avoid overloading CPU
            elapsed = time.monotonic() - loop_start
            sleep_time = 0.033 - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        if picam2:
            picam2.stop()
        if cap:
            cap.release()
        print("[WebStreamer] Camera capture thread stopped.")


# ───────────────────────────────────────────────────────────
# INTEGRATED MODE: To be spawned as a process by main.py
# ───────────────────────────────────────────────────────────
def web_streamer_process(
    system_running,
    shm_name,
    frame_lock,
    frame_width,
    frame_height,
    sign_id,
    sign_confidence,
    lane_offset=None,
    lane_curvature=None,
    lane_detected=None,
    obstacle_dist=None,
    voice_command=None,
    port=5000
):
    """
    Process Target for main.py integration.
    Reads frames from SharedMemory and telemetry values from multiprocessing.Value
    variables, hosting the web telemetry and video dashboard.
    """
    from multiprocessing import shared_memory
    from contracts import SignType, VoiceCommand
    global state

    print(f"[WebStreamer] Starting Integrated Web Streamer on port {port}...")

    # Attach to Shared Memory block for frames
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
        shared_frame = np.ndarray(
            (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
        )
    except Exception as e:
        print(f"[WebStreamer] ERROR: Could not attach to shared memory '{shm_name}': {e}")
        return

    # Start HTTP Web Server
    server = HTTPServer(('0.0.0.0', port), TelemetryHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Mapping helpers
    sign_id_to_str = {
        0: "NONE",
        1: "LEFT",
        2: "RIGHT",
        3: "STOP"
    }

    voice_cmd_to_str = {
        0: "NONE",
        1: "START",
        2: "STOP",
        3: "PAUSE",
        4: "CONTINUE"
    }

    fps_time = time.monotonic()
    frame_counter = 0

    try:
        while system_running.value:
            loop_start = time.monotonic()

            # 1. Read frame from SharedMemory (zero-copy)
            with frame_lock:
                frame = shared_frame.copy()

            # 2. Draw overlay if sign is active
            active_sign_id = sign_id.value
            active_conf = sign_confidence.value
            
            # Since sign detector writes outputs directly to shared memory,
            # we draw the status indicator if confidence is above our threshold.
            if active_sign_id > 0 and active_conf >= 0.5:
                # Place a telemetry card overlay on the video itself
                cv2.putText(
                    frame, 
                    f"DETECTED: {sign_id_to_str.get(active_sign_id, 'UNKNOWN')} ({active_conf*100:.1f}%)", 
                    (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (0, 0, 255) if active_sign_id == 3 else (0, 255, 0), 
                    2, 
                    cv2.LINE_AA
                )
                # Draw a clean border on the video to show detection is active
                border_color = (0, 0, 255) if active_sign_id == 3 else (255, 120, 0)
                cv2.rectangle(frame, (5, 5), (frame_width-5, frame_height-5), border_color, 4)

            # 3. Compress to JPEG
            _, jpeg_buffer = cv2.imencode('.jpg', frame)
            jpeg_bytes = jpeg_buffer.tobytes()

            # 4. Read other telemetry values if available
            offset_val = lane_offset.value if lane_offset else 0.0
            curve_val = lane_curvature.value if lane_curvature else 0.0
            detected_val = bool(lane_detected.value) if lane_detected else False
            obstacle_val = obstacle_dist.value if obstacle_dist else 999.0
            voice_val = voice_cmd_to_str.get(voice_command.value, "NONE") if voice_command else "NONE"

            # 5. Measure FPS
            frame_counter += 1
            now = time.monotonic()
            elapsed_fps = now - fps_time
            current_fps = state["fps"]
            if elapsed_fps >= 1.0:
                current_fps = frame_counter / elapsed_fps
                frame_counter = 0
                fps_time = now

            # 6. Update Web Server State
            with state_lock:
                state["latest_frame_jpeg"] = jpeg_bytes
                state["fps"] = current_fps
                # Since we aren't doing NCNN inference in this process (Process 2 does it), 
                # we display latency as 0.0 or just a dummy.
                state["latency_ms"] = 0.0
                state["detected_class"] = sign_id_to_str.get(active_sign_id, "NONE")
                state["confidence"] = active_conf
                state["lane_offset"] = offset_val
                state["lane_curvature"] = curve_val
                state["lane_detected"] = detected_val
                state["obstacle_dist"] = obstacle_val
                state["voice_command"] = voice_val

            # Cap frame rate to limit CPU and memory usage
            elapsed = time.monotonic() - loop_start
            sleep_time = 0.033 - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        with state_lock:
            state["running"] = False
        server.shutdown()
        shm.close()
        print("[WebStreamer] Integrated Web Streamer stopped.")


if __name__ == "__main__":
    # If run directly as a script, start Standalone Mode
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server = HTTPServer(('0.0.0.0', port), TelemetryHandler)
    print(f"\n========================================================")
    print(f"🚀 PiCar-X Vision Server starting in STANDALONE mode")
    print(f"   Address: http://localhost:{port}")
    print(f"   Or on local network: http://<pi-ip-address>:{port}")
    print(f"========================================================\n")

    # Start camera capture & inference background thread
    cam_thread = threading.Thread(target=standalone_inference_loop, daemon=True)
    cam_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebStreamer] Shutting down server...")
    finally:
        with state_lock:
            state["running"] = False
        server.shutdown()
        cam_thread.join(timeout=2.0)
        print("[WebStreamer] Clean shutdown complete.")

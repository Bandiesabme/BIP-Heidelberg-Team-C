#!/usr/bin/env python3
"""
capture_drive_web.py  -  Live view + DRIVE controls + sign capture (PiCar-X).

Run this ON THE PI. Opens the camera once, streams it live to a web page, and
gives you:
  - drive controls (forward / back / left / right / stop) via on-screen buttons
    AND keyboard (W A S D, Space = stop)
  - sign-capture buttons (Save Left / Right / Stop / None) that save the current
    frame into dataset/<class>/

So you can drive the car around the track and grab sign photos from realistic
positions, all from one browser tab.

USAGE
-----
    python3 capture_drive_web.py
Then on your laptop open:   http://<pi-ip>:8000   (Pi IP:  hostname -I )

DRIVE KEYS (while the browser tab is focused)
    W forward   S back   A steer left   D steer right   Space / X = STOP
    Forward/back run only while the key is held; releasing stops the car.

SAVE: click Save Left / Right / Stop / None  -> dataset/left etc.

SAFETY
    - Car stops when you release a drive key and when you quit (Ctrl+C).
    - Start with a LOW speed; raise SPEED below once you trust it.
    - Put the car on blocks for the first test so wheels spin free.
"""

import os
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
from picamera2 import Picamera2

# --- car control ----------------------------------------------------------
SPEED = 30          # 0-100. Start low. Raise once you trust the controls.
STEER_ANGLE = 25    # degrees for a left/right turn (max ~30)

px = None
try:
    from picarx import Picarx
    px = Picarx()
    px.set_dir_servo_angle(0)
    px.stop()
except Exception as e:
    print(f"[warn] Picarx not available ({e}). Camera/capture still work, "
          f"but drive controls won't move the car.")

CLASSES = ["left", "right", "stop", "none"]
ROOT = "dataset"
FRAME_W, FRAME_H = 640, 480
PORT = 8000

_lock = threading.Lock()
_latest_jpeg = None
_latest_frame = None


def ensure_dirs():
    for c in CLASSES:
        os.makedirs(os.path.join(ROOT, c), exist_ok=True)


def count_per_class():
    return {c: len(os.listdir(os.path.join(ROOT, c))) for c in CLASSES}


def camera_loop(picam2):
    global _latest_jpeg, _latest_frame
    while True:
        frame = picam2.capture_array()
        ok, jpeg = cv2.imencode(".jpg", frame)
        if ok:
            with _lock:
                _latest_frame = frame
                _latest_jpeg = jpeg.tobytes()
        time.sleep(0.03)


def save_current(label):
    with _lock:
        frame = None if _latest_frame is None else _latest_frame.copy()
    if frame is None:
        return None
    ts = datetime.now().strftime("%H%M%S_%f")
    path = os.path.join(ROOT, label, f"{label}_{ts}.jpg")
    cv2.imwrite(path, frame)
    return path


# --- drive command handling -------------------------------------------------
def do_drive(cmd):
    if px is None:
        return
    if cmd == "forward":
        px.set_dir_servo_angle(0)
        px.forward(SPEED)
    elif cmd == "back":
        px.set_dir_servo_angle(0)
        px.backward(SPEED)
    elif cmd == "left":
        px.set_dir_servo_angle(-STEER_ANGLE)
        px.forward(SPEED)
    elif cmd == "right":
        px.set_dir_servo_angle(STEER_ANGLE)
        px.forward(SPEED)
    elif cmd == "stop":
        px.stop()
        px.set_dir_servo_angle(0)


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>PiCar-X Capture + Drive</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: dark; }
  body { margin:0; font-family:system-ui,sans-serif; background:#15171c;
         color:#e8eaed; display:flex; flex-direction:column; align-items:center;
         gap:14px; padding:16px; }
  h1 { font-size:1.05rem; font-weight:600; margin:0; }
  #feed { width:min(92vw,720px); aspect-ratio:4/3; background:#000;
          border-radius:10px; border:1px solid #2a2e37; object-fit:cover; }
  .row { width:min(92vw,720px); }
  .label { font-size:.78rem; text-transform:uppercase; letter-spacing:.08em;
           color:#7e828c; margin:4px 2px; }
  .save { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
  .drive { display:grid; grid-template-columns:repeat(3,1fr); gap:10px;
           max-width:340px; }
  button { padding:16px 0; font-size:1rem; font-weight:600; cursor:pointer;
           border:none; border-radius:10px; color:#0d0f12; user-select:none; }
  .left{background:#7cc4ff;} .right{background:#9be08a;}
  .stop{background:#ff8a8a;} .none{background:#c9ccd3;}
  .d{background:#3a3f4b;color:#e8eaed;} .d.go{background:#5566ff;color:#fff;}
  .d.halt{background:#ff8a8a;color:#0d0f12;}
  .blank{visibility:hidden;}
  button:active{transform:translateY(1px);filter:brightness(.9);}
  #counts{font-variant-numeric:tabular-nums;font-size:.92rem;color:#aeb2bb;}
  #toast{min-height:1.2em;font-size:.85rem;color:#9be08a;}
  kbd{background:#2a2e37;border-radius:4px;padding:1px 6px;font-size:.8rem;}
</style></head><body>
  <h1>PiCar-X &mdash; capture + drive</h1>
  <img id="feed" src="/stream">

  <div class="row">
    <div class="label">Drive &nbsp; (<kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>, <kbd>Space</kbd>=stop)</div>
    <div class="drive">
      <span class="blank"></span>
      <button class="d go" onmousedown="drive('forward')" onmouseup="drive('stop')"
              ontouchstart="drive('forward')" ontouchend="drive('stop')">▲ W</button>
      <span class="blank"></span>
      <button class="d" onmousedown="drive('left')" onmouseup="drive('stop')"
              ontouchstart="drive('left')" ontouchend="drive('stop')">◀ A</button>
      <button class="d halt" onclick="drive('stop')">STOP</button>
      <button class="d" onmousedown="drive('right')" onmouseup="drive('stop')"
              ontouchstart="drive('right')" ontouchend="drive('stop')">D ▶</button>
      <span class="blank"></span>
      <button class="d" onmousedown="drive('back')" onmouseup="drive('stop')"
              ontouchstart="drive('back')" ontouchend="drive('stop')">▼ S</button>
      <span class="blank"></span>
    </div>
  </div>

  <div class="row">
    <div class="label">Save sign</div>
    <div class="save">
      <button class="left"  onclick="save('left')">Save Left</button>
      <button class="right" onclick="save('right')">Save Right</button>
      <button class="stop"  onclick="save('stop')">Save Stop</button>
      <button class="none"  onclick="save('none')">Save None</button>
    </div>
  </div>

  <div id="counts">loading...</div>
  <div id="toast"></div>
<script>
  function drive(cmd){ fetch('/drive?cmd='+cmd, {method:'POST'}); }
  async function save(label){
    const r = await fetch('/save?label='+label, {method:'POST'});
    const d = await r.json();
    document.getElementById('toast').textContent = 'saved '+label+'  ->  '+d.path;
    refresh();
  }
  async function refresh(){
    const r = await fetch('/counts'); const d = await r.json();
    document.getElementById('counts').textContent =
      'left '+d.left+'   right '+d.right+'   stop '+d.stop+'   none '+d.none;
  }
  // keyboard: hold to move, release to stop
  const held = {};
  document.addEventListener('keydown', e=>{
    const k = e.key.toLowerCase();
    if(held[k]) return; held[k]=true;
    if(k==='w') drive('forward');
    else if(k==='s') drive('back');
    else if(k==='a') drive('left');
    else if(k==='d') drive('right');
    else if(k===' '||k==='x'){ drive('stop'); e.preventDefault(); }
  });
  document.addEventListener('keyup', e=>{
    const k = e.key.toLowerCase(); held[k]=false;
    if(['w','s','a','d'].includes(k)) drive('stop');
  });
  refresh(); setInterval(refresh, 4000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._bytes(PAGE.encode(), "text/html")
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with _lock:
                        jpg = _latest_jpeg
                    if jpg is not None:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(jpg)}\r\n\r\n".encode())
                        self.wfile.write(jpg); self.wfile.write(b"\r\n")
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/counts":
            self._json(count_per_class())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/save"):
            label = self.path.split("label=")[1].split("&")[0] if "label=" in self.path else "none"
            if label not in CLASSES:
                self._json({"error": "bad label"}, 400); return
            self._json({"path": save_current(label) or "no frame yet"})
        elif self.path.startswith("/drive"):
            cmd = self.path.split("cmd=")[1].split("&")[0] if "cmd=" in self.path else "stop"
            do_drive(cmd)
            self._json({"ok": True, "cmd": cmd})
        else:
            self.send_error(404)

    def _bytes(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        import json
        self._bytes(json.dumps(obj).encode(), "application/json", code)


def main():
    ensure_dirs()
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (FRAME_W, FRAME_H)}))
    picam2.start()
    time.sleep(1)

    threading.Thread(target=camera_loop, args=(picam2,), daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(__doc__)
    print(f"\nOpen  http://<pi-ip>:{PORT}  on your laptop (IP: hostname -I)")
    print("Ctrl+C to quit (motors will stop).\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        if px:
            px.stop()
            px.set_dir_servo_angle(0)
        picam2.stop()
        print("\nFinal counts:", count_per_class())
        print("Done. Move the 'dataset' folder to your laptop for Roboflow.")


if __name__ == "__main__":
    main()
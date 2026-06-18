# Auto-driving Robot Controller

A Python-based autonomous driving project that features lane detection, stop sign recognition (via YOLO), and a web-based dashboard for real-time telemetry, video streaming, and parameter tuning.

## Features

- **Web Dashboard**: A built-in HTTP server (`app.py`) providing a user interface at `http://localhost:5001`.
- **Real-time Video Streaming**: View both the raw camera feed and the processed feed with lane overlays and status text directly in the browser.
- **Lane Detection**: Uses computer vision to detect lanes and calculate steering offset.
- **Stop Sign Detection**: Utilizes a YOLO model (`best.pt`) to detect stop signs and trigger a vehicle stop when the sign is close enough.
- **Telemetry & Control API**: Live JSON API for reading robot status and adjusting parameters on the fly (speed, steering limits, white balance thresholds, camera pan/tilt, etc.).
- **Hardware Support**: Designed for Raspberry Pi (using `Picamera2`) and PiCar-X hardware, with a seamless fallback to standard USB webcams via OpenCV.

## Project Structure

- `app.py`: The main entry point. Runs the multi-threaded web server and the background camera capture loop.
- `autodrive.py`: Handles the motor controls, steering angles, and interfaces with the robotic chassis (PiCar-X).
- `lane_decetion.py`: Contains the logic for the `LaneDetector`.
- `sign_detection.py`: Contains the `SignDetector` logic, utilizing the YOLO framework.
- `index.html`: The frontend web interface served by `app.py`.
- `best.pt`: The trained YOLO weights file used for recognizing stop signs.

## Prerequisites

- Python 3.x
- OpenCV (`cv2`)
- YOLO dependencies (e.g., `ultralytics`)
- `picamera2` (if running on a Raspberry Pi)
- PiCar-X or compatible motor driver libraries (depending on `autodrive.py` implementation)

## How to Run

1. Ensure all dependencies are installed and the hardware is connected.
2. Run the main application script:

```bash
python app.py
```

3. Open a web browser and navigate to `http://localhost:5001` to view the dashboard and control the robot.

## Live Configuration

You can adjust driving behaviors directly from the web interface, which sends requests to the `/api/set` endpoint. Adjustable parameters include:
- Autodrive toggle (Enable/Disable)
- Target speed and maximum steering angle
- Lane detection thresholds (white threshold, ROI top ratio, follow offset)
- Stop sign trigger size (how close the sign must be before stopping)
- Camera pan and tilt angles

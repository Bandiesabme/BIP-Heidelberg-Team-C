  # PiCar-X Autonomous Navigation Challenge 🚗💨
  
  An autonomous vehicle project for a 4-day hackathon. The objective is to program the SunFounder PiCar-X to autonomously navigate a mimicked road track and respond correctly to traffic signs using Computer Vision and fallback hardware sensors.
  
---
## 🌿 Git Branching & Workflow Rules

To prevent code overrides and messy merge conflicts, we use a strict **3-tier branch structure**:

* **🟢 1. main branch (Production Code)**
  * *Only bug-free, track-tested code lives here. Direct pushes are blocked.*
  * └── **🟠 2. develop branch (Integration Sandbox)**
    * *Where pairs open PRs to combine and test their logic together.*
    * ├── **🔵 feature/lane-hsv** (Pair B Workspace)
    * ├── **🔵 feature/picar-motion** (Pair A Workspace)
    * └── **🔵 feature/sign-contours** (Pair C Workspace)

### 🚨 The 3 Rules of Engagement:
1. **Never work on `main` or `develop` directly.** Always spin up a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name



   # PiCar-X Autonomous Challenge: Software Architecture Blueprint
**SRH University of Applied Sciences Heidelberg — BIP Challenge**

This document provides a highly modular, multi-threaded software architecture blueprint for a 6-person team to implement a robust autonomous lane-following and traffic-aware robot car within a strict 48-hour deadline.

---

## 1. System Architecture Overview

To eliminate development bottlenecks and merge conflicts, the system uses an asynchronous **Threaded Pipeline Pattern** decoupled by thread-safe communication queues (`queue.Queue`). Each major functional unit runs as a standalone background thread.

```text
                         +------------------------+
                         |      Voice Control     |
                         |     (Bonus Module)     |
                         +-----------+------------+
                                     | (voice_queue)
                                     v
+------------------+     +-----------+------------+     +-------------------+
|  Lane Detection  |---->|                        |<----+  Obstacle Sensor  |
|   (lane_queue)   |     |      Central Brain     |     |  (obstacle_queue) |
+------------------+     |     (State Machine)    |     +-------------------+
                         |                        |
+------------------+     +-----------+------------+
| Sign Recognition |---->|           |            |
|   (sign_queue)   |     +-----------+------------+
+------------------+                 | (motor_queue)
                                     v
                         +-----------+------------+
                         |     Hardware Drive     |
                         |   (Low-Level Actuation)|
                         +------------------------+

```
### Communication Protocols & Data Contracts
Threads communicate via lightweight, non-blocking Python primitives inside thread-safe FIFO queues to prevent CPU starvation and race conditions:

| Data Flow Channel | Producer Module | Consumer Module | Data Format / Payload Schema |
| :--- | :--- | :--- | :--- |
| `lane_queue` | Lane Detection | Central Brain | `float`: Normalized lateral error index between `-1.0` (far left) and `+1.0` (far right). `0.0` represents perfect center alignment. |
| `sign_queue` | Sign Recognition | Central Brain | `str`: Exact enum-string match: `"LEFT"`, `"RIGHT"`, `"STOP"`, or `"NONE"`. |
| `obstacle_queue` | Obstacle Sensor | Central Brain | `bool`: Emergency flag. `True` if a physical object is detected within critical stopping envelope ($<20\text{ cm}$). |
| `voice_queue` | Voice Control | Central Brain | `str`: Command token parsed from microphone: `"start"`, `"stop"`, `"pause"`, `"continue"`. |
| `motor_queue` | Central Brain | Hardware Drive | `dict`: Explicit target actuation payload: `{"speed": int [-100 to 100], "steering": int [-40 to 40]}`. |


---
## 2. Directory Structure & Team Allocation

This file structure provides strict ownership boundaries so that all 6 team members can code concurrently in isolated files without breaking the primary orchestration loop.

```text
picarx_project/
│
├── main.py                 # Systems Orchestrator & Thread Monitor (Integrated Framework)
├── config.py               # Shared global thresholds, pins, speeds, and PID tunings
│
└── modules/
    ├── __init__.py         # Package initialization namespaces
    ├── hardware_drive.py   # [Person 1] Low-level Picarx motor/servo abstraction
    ├── lane_detection.py   # [Person 2] OpenCV Color/Contour Lane Processing
    ├── sign_recognition.py # [Person 3] OpenCV Pattern/Color Traffic Sign Classifier
    ├── obstacle_sensor.py  # [Person 4] Ultrasonic HC-SR04 Hardware Polling
    ├── voice_control.py    # [Person 5] Bonus: Speech Recognition & Command Engine
    └── brain.py            # [Person 6] Central Finite State Machine (FSM) & Control System

```

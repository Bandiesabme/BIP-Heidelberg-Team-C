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



### 3.2 Process Layout

```
┌─────────────────────────────────────────────────────────┐
│                    RASPBERRY PI 4                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  PROCESS 1   │  │  PROCESS 2   │  │  PROCESS 3   │  │
│  │  Core 0      │  │  Core 1      │  │  Core 2      │  │
│  │              │  │              │  │              │  │
│  │  Camera +    │  │  YOLO Sign   │  │  Voice       │  │
│  │  OpenCV      │  │  Detection   │  │  Commands    │  │
│  │  Lane        │  │              │  │  +           │  │
│  │  Detection   │  │  Runs on     │  │  Ultrasonic  │  │
│  │              │  │  every Nth   │  │  Sensor      │  │
│  │  ~30 FPS     │  │  frame       │  │              │  │
│  │              │  │  ~10-15 FPS  │  │  ~10 Hz      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌─────────────────────────────────────────────────┐    │
│  │              SHARED MEMORY (atomic)             │    │
│  │  multiprocessing.Value (ctypes)                 │    │
│  │                                                 │    │
│  │  lane_offset    : c_double  (pixels from center)│    │
│  │  lane_curvature : c_double  (curve radius)      │    │
│  │  lane_detected  : c_bool                        │    │
│  │  sign_id        : c_int     (0=none,1=L,2=R,3=S)│   │
│  │  sign_confidence: c_double                      │    │
│  │  obstacle_dist  : c_double  (cm)                │    │
│  │  voice_command  : c_int     (0=none,1-4=cmds)   │    │
│  │  system_running : c_bool    (kill switch)       │    │
│  └────────────────────┬────────────────────────────┘    │
│                       │                                 │
│                       ▼                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │              PROCESS 4 — Core 3                 │    │
│  │              ORCHESTRATOR (main.py)              │    │
│  │                                                 │    │
│  │  1. Read shared memory → build SensorState DTO  │    │
│  │  2. Pass DTO to Brain.decide_next_action()      │    │
│  │  3. Brain returns ActionCommand DTO             │    │
│  │  4. Execute ActionCommand via picarx            │    │
│  │  5. Sleep to maintain 30 Hz loop                │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘

# PiCar-X Autonomous Driving — Complete Knowledge Base

> **Purpose**: This document is the single source of truth for the PiCar-X autonomous driving project. It is designed to be fed to any AI coding assistant so that every team member gets architecturally consistent, conflict-free code regardless of which subsystem they are working on.

---

## 1. Project Overview

### 1.1 Objective
Build an autonomous RC car (SunFounder PiCar-X) that can:
1. **Follow lane markings** on a simple indoor track (60 points)
2. **Recognize and react to 3 traffic signs**: Left, Right, Stop (20 points)
3. **Bonus**: Voice commands (Start/Stop/Pause/Continue) and obstacle avoidance (bonus points)

### 1.2 Evaluation Criteria
The project is **not** judged on code volume or model complexity. It is judged on:
- **Reliability** — the car must complete a full autonomous lap without crashing
- **Robust engineering** — graceful handling of edge cases
- **Smart design choices** — appropriate tool for each job
- **Effective teamwork** — clean separation of concerns, no merge conflicts

### 1.3 Team Size
6 people. The architecture must allow parallel development with zero coupling between subsystems.

---

## 2. Hardware Platform

### 2.1 Compute
| Component | Spec |
|---|---|
| Board | Raspberry Pi 4 Model B |
| CPU | Broadcom BCM2711, Quad-core Cortex-A72, 1.8 GHz |
| RAM | 4 GB LPDDR4 (assume worst case) |
| GPU | VideoCore VI (not usable for general ML inference) |
| OS | Raspberry Pi OS (Debian Bookworm, 64-bit) |

### 2.2 PiCar-X Hardware
| Component | Interface | Notes |
|---|---|---|
| Camera | CSI ribbon / USB webcam | 640×480 @ 30 FPS typical; use `picamera2` or OpenCV `VideoCapture` |
| Steering Servo | PWM via PCA9685 (I²C) | Controlled through `picarx` Python library |
| Drive Motor (DC) | PWM via PCA9685 (I²C) | Forward/backward speed control |
| Ultrasonic Sensor (HC-SR04) | GPIO (Trigger + Echo) | Front-facing, range ~2–400 cm |
| Grayscale Sensors (×3) | ADC via I²C | Line-following sensors on the underside (optional, can supplement camera) |
| Speaker | 3.5mm / I²S | For audio feedback |
| Microphone | USB | For voice commands |

### 2.3 PiCar-X Python Library
SunFounder provides `picarx` — a high-level Python library:

```python
from picarx import Picarx

px = Picarx()

# Steering: angle in degrees, negative = left, positive = right
px.set_dir_servo_angle(0)    # straight
px.set_dir_servo_angle(-30)  # turn left 30°
px.set_dir_servo_angle(30)   # turn right 30°

# Driving: speed 0–100, positive = forward, negative = backward
px.forward(30)     # drive forward at speed 30
px.backward(20)    # reverse at speed 20
px.stop()          # stop motors

# Camera servo (pan/tilt)
px.set_camera_servo1_angle(0)  # pan
px.set_camera_servo2_angle(0)  # tilt

# Ultrasonic
from picarx import Picarx
import time
px = Picarx()
distance = px.ultrasonic.read()  # returns cm (float)

# Grayscale sensors
gm_val_list = px.get_grayscale_data()  # returns [left, center, right]
```

> [!IMPORTANT]
> All hardware I/O (`picarx` calls, GPIO, PWM) must happen in **one single process** — the Orchestrator (Process 4 / Main). Calling `picarx` from multiple processes simultaneously will cause I²C bus collisions and undefined behavior.

---

## 3. Architecture

### 3.1 Design Philosophy
The Raspberry Pi 4 has **4 CPU cores**. Python's **GIL** (Global Interpreter Lock) makes `threading` useless for CPU-bound work. Therefore, the architecture uses **`multiprocessing`** to pin one major workload per core.

Communication between processes uses **`multiprocessing.Value`** (atomic shared memory backed by `ctypes`) — **not** `queue.Queue`, which has lock contention overhead.

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
```

### 3.3 Process Responsibilities

| Process | Core | Module | Input | Output (Shared Memory) | Target Rate |
|---|---|---|---|---|---|
| P1: Lane Detection | 0 | `vision/lane_detector.py` | Camera frames | `lane_offset`, `lane_curvature`, `lane_detected` | 30 FPS |
| P2: Sign Detection | 1 | `vision/sign_detector.py` | Camera frames (shared or separate capture) | `sign_id`, `sign_confidence` | 10–15 FPS |
| P3: Sensors & Voice | 2 | `sensors/voice.py`, `sensors/ultrasonic.py` | Microphone, HC-SR04 | `voice_command`, `obstacle_dist` | 10 Hz |
| P4: Orchestrator | 3 | `main.py` | Reads all shared memory | PWM signals to motors/servos | 30 Hz |

### 3.4 Camera Sharing Strategy

Running two OpenCV `VideoCapture` instances on the same camera will fail. Two options:

**Option A (Recommended): Single-capture with `SharedMemory` + numpy**
- P1 captures frames and writes the latest frame to a `multiprocessing.shared_memory.SharedMemory` block.
- Both P1 and P2 wrap the same memory block as a `numpy.ndarray` — **zero-copy**, ~0.5ms per frame.
- Use a `multiprocessing.Lock` only around the `np.copyto()` write / `.copy()` read.

> [!CAUTION]
> **Do NOT use `multiprocessing.Array` with `.flatten().tolist()`** — converting 921,600 pixels to a Python list takes ~100ms, destroying your 30 FPS target. `SharedMemory` + numpy is 200× faster.

**Option B: Two separate captures**
- Use a CSI camera for P1 (via `picamera2`) and a USB webcam for P2.
- More hardware, but zero contention.

---

## 4. Contracts (Data Transfer Objects)

All inter-process communication is defined through these DTOs. **Every team member must use these exact field names and types.**

### 4.1 `contracts.py`

```python
"""
contracts.py — Data Transfer Objects for inter-process communication.

These dataclasses define the ONLY data structures that cross process
boundaries. All fields map 1:1 to multiprocessing.Value shared memory.

DO NOT import picarx, OpenCV, or any heavy library here.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class SignType(IntEnum):
    """Traffic sign classifications."""
    NONE = 0
    LEFT = 1
    RIGHT = 2
    STOP = 3


class VoiceCommand(IntEnum):
    """Voice command classifications."""
    NONE = 0
    START = 1
    STOP = 2
    PAUSE = 3
    CONTINUE = 4


class SystemState(IntEnum):
    """Top-level system state for the finite state machine."""
    IDLE = 0        # Waiting for START command
    DRIVING = 1     # Normal lane following
    TURNING = 2     # Executing a sign-triggered turn
    STOPPED = 3     # STOP sign or voice STOP
    PAUSED = 4      # Voice PAUSE (motors off, resume possible)
    AVOIDING = 5    # Obstacle avoidance maneuver


@dataclass(frozen=True)
class SensorState:
    """
    Immutable snapshot of all sensor data at a single point in time.
    
    Built by the Orchestrator by reading shared memory atomically.
    Passed to Brain.decide_next_action() — the Brain never touches
    shared memory or hardware directly.
    
    Fields:
        lane_offset:     Pixels from image center. Negative = car is left of center.
        lane_curvature:  Inverse radius of detected curve. 0 = straight.
        lane_detected:   True if lane markings are visible.
        sign_id:         The most recently detected sign (SignType enum).
        sign_confidence: YOLO confidence score [0.0, 1.0].
        obstacle_dist_cm: Distance to nearest obstacle in cm. 999.0 = no obstacle.
        voice_command:   The most recently received voice command.
        current_state:   The current SystemState.
        speed:           Current motor speed (0–100).
        steering_angle:  Current steering angle in degrees (-30 to +30).
    """
    lane_offset: float = 0.0
    lane_curvature: float = 0.0
    lane_detected: bool = False
    sign_id: int = SignType.NONE
    sign_confidence: float = 0.0
    obstacle_dist_cm: float = 999.0
    voice_command: int = VoiceCommand.NONE
    current_state: int = SystemState.IDLE
    speed: float = 0.0
    steering_angle: float = 0.0


@dataclass(frozen=True)
class ActionCommand:
    """
    Immutable action command returned by the Brain.
    
    The Orchestrator translates this directly into picarx calls.
    The Brain must NEVER call picarx directly.
    
    Fields:
        steering_angle: Target servo angle in degrees. Range: -30 to +30.
                        Negative = left, Positive = right, 0 = straight.
        speed:          Target motor speed. Range: 0 to 100.
                        0 = stopped.
        direction:      1 = forward, -1 = backward, 0 = stop.
        new_state:      The state the system should transition to.
        sign_consumed:  If True, the Orchestrator resets sign_id to NONE
                        after executing this command (prevents re-triggering).
        voice_consumed: If True, the Orchestrator resets voice_command to NONE.
    """
    steering_angle: float = 0.0
    speed: float = 0.0
    direction: int = 1
    new_state: int = SystemState.DRIVING
    sign_consumed: bool = False
    voice_consumed: bool = False
```

### 4.2 Shared Memory Layout

These are the `multiprocessing.Value` variables created in `main.py` and passed to each worker process:

```python
from multiprocessing import Value
from ctypes import c_double, c_bool, c_int

# Lane detection outputs (written by P1)
lane_offset     = Value(c_double, 0.0)
lane_curvature  = Value(c_double, 0.0)
lane_detected   = Value(c_bool, False)

# Sign detection outputs (written by P2)
sign_id         = Value(c_int, 0)       # SignType enum value
sign_confidence = Value(c_double, 0.0)

# Sensor outputs (written by P3)
obstacle_dist   = Value(c_double, 999.0)
voice_command   = Value(c_int, 0)       # VoiceCommand enum value

# System control (read/written by P4, read by all)
system_running  = Value(c_bool, True)   # Global kill switch
```

> [!CAUTION]
> **Thread-safety rule**: Each `Value` has exactly **one writer process**. Multiple readers are safe. Never have two processes writing to the same `Value`.

---

## 5. Brain — Subsumption Architecture

### 5.1 What Is Subsumption?
A priority-layered decision system inspired by Rodney Brooks' subsumption architecture. Higher-priority behaviors **override** lower ones. The brain evaluates layers top-down and returns the **first** matching action.

### 5.2 Priority Layers (Highest → Lowest)

```
Layer 0 (HIGHEST):  Voice Command Override
                    → STOP / PAUSE immediately halt the car
                    → START / CONTINUE resume driving

Layer 1:            Obstacle Emergency Stop
                    → If obstacle_dist_cm < OBSTACLE_STOP_THRESHOLD
                    → Full stop, enter AVOIDING state

Layer 2:            Traffic Sign Reaction
                    → STOP sign: decelerate and stop for N seconds
                    → LEFT sign: execute left turn sequence
                    → RIGHT sign: execute right turn sequence

Layer 3:            Lane Following (PID)
                    → Use lane_offset to compute steering via PID
                    → Use lane_curvature to modulate speed

Layer 4 (LOWEST):   Default / Fallback
                    → If no lane detected: slow down, drive straight
                    → Safety crawl behavior
```

### 5.3 `brain/interface.py`

```python
"""
brain/interface.py — Abstract Base Class for the autonomous brain.

Any brain implementation must conform to this interface.
This ensures the Orchestrator is decoupled from the decision logic.
"""

from abc import ABC, abstractmethod
from contracts import SensorState, ActionCommand


class AutonomousBrain(ABC):
    """
    The decision-making interface for the PiCar-X.
    
    Contract:
    - Input: SensorState (immutable snapshot of all sensor data)
    - Output: ActionCommand (immutable action to execute)
    - Must be PURE: no side effects, no hardware calls, no blocking I/O
    - Must complete in < 5ms (it runs in the 30Hz main loop)
    """

    @abstractmethod
    def decide_next_action(self, state: SensorState) -> ActionCommand:
        """
        Given the current sensor state, decide what the car should do.
        
        Args:
            state: Immutable snapshot of all sensor readings.
            
        Returns:
            ActionCommand with steering, speed, direction, and state transition.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state (e.g., PID integrator, turn sequence counters)."""
        ...
```

### 5.4 `brain/subsumption.py` — Implementation Skeleton

```python
"""
brain/subsumption.py — Subsumption-based decision brain.

Priority cascade: Voice > Obstacle > Sign > Lane > Fallback
"""

from contracts import (
    SensorState, ActionCommand,
    SignType, VoiceCommand, SystemState
)
from brain.interface import AutonomousBrain
from brain.pid import PIDController  # see Section 6


# ── Tunable Constants ──────────────────────────────────────
OBSTACLE_STOP_CM = 25.0          # Emergency stop distance
OBSTACLE_SLOW_CM = 50.0          # Begin slowing down
SIGN_CONFIDENCE_THRESHOLD = 0.6  # Ignore low-confidence detections
STOP_SIGN_WAIT_SECONDS = 3.0     # How long to wait at a stop sign
TURN_DURATION_SECONDS = 2.0      # How long a turn maneuver lasts
BASE_SPEED = 30                  # Normal cruising speed (0–100)
MIN_SPEED = 15                   # Minimum speed in curves
MAX_STEERING = 30                # Max steering angle (degrees)
FALLBACK_SPEED = 15              # Speed when no lane is detected


class SubsumptionBrain(AutonomousBrain):
    """Subsumption architecture with priority-layered behaviors."""

    def __init__(self):
        self.pid = PIDController(kp=0.8, ki=0.01, kd=0.3)
        self._turn_start_time: float = 0.0
        self._stop_start_time: float = 0.0

    def decide_next_action(self, state: SensorState) -> ActionCommand:
        """
        Evaluate layers top-down. First matching layer wins.
        """

        # ── Layer 0: Voice Command Override ──
        if state.voice_command == VoiceCommand.STOP:
            return ActionCommand(
                speed=0, direction=0,
                new_state=SystemState.STOPPED,
                voice_consumed=True
            )
        
        if state.voice_command == VoiceCommand.PAUSE:
            return ActionCommand(
                speed=0, direction=0,
                new_state=SystemState.PAUSED,
                voice_consumed=True
            )
        
        if state.voice_command in (VoiceCommand.START, VoiceCommand.CONTINUE):
            return ActionCommand(
                speed=BASE_SPEED, direction=1,
                new_state=SystemState.DRIVING,
                voice_consumed=True
            )

        # If system is STOPPED or PAUSED, do nothing until voice resumes
        if state.current_state in (SystemState.STOPPED, SystemState.PAUSED, 
                                     SystemState.IDLE):
            return ActionCommand(speed=0, direction=0, 
                                 new_state=state.current_state)

        # ── Layer 1a: Obstacle Emergency Stop ──
        if state.obstacle_dist_cm < OBSTACLE_STOP_CM:
            return ActionCommand(
                speed=0, direction=0,
                new_state=SystemState.AVOIDING
            )

        # ── Layer 1b: Obstacle Caution Zone (gradual slowdown) ──
        if state.obstacle_dist_cm < OBSTACLE_SLOW_CM:
            # Linearly reduce speed: full speed at SLOW_CM, MIN_SPEED at STOP_CM
            scale = (state.obstacle_dist_cm - OBSTACLE_STOP_CM) / (
                OBSTACLE_SLOW_CM - OBSTACLE_STOP_CM
            )
            cautious_speed = max(MIN_SPEED, BASE_SPEED * scale)
            # Still follow the lane, just slower
            steering = 0.0
            if state.lane_detected:
                steering = self.pid.compute(setpoint=0.0, measured=state.lane_offset)
                steering = max(-MAX_STEERING, min(MAX_STEERING, steering))
            return ActionCommand(
                steering_angle=steering,
                speed=cautious_speed,
                direction=1,
                new_state=SystemState.DRIVING
            )

        # ── Layer 2: Traffic Sign Reaction ──
        if (state.sign_id != SignType.NONE 
                and state.sign_confidence >= SIGN_CONFIDENCE_THRESHOLD):
            return self._handle_sign(state)

        # ── Layer 3: Lane Following (PID) ──
        if state.lane_detected:
            return self._lane_follow(state)

        # ── Layer 4: Fallback ──
        return ActionCommand(
            steering_angle=0.0,
            speed=FALLBACK_SPEED,
            direction=1,
            new_state=SystemState.DRIVING
        )

    def _handle_sign(self, state: SensorState) -> ActionCommand:
        """React to a detected traffic sign."""
        if state.sign_id == SignType.STOP:
            return ActionCommand(
                speed=0, direction=0,
                new_state=SystemState.STOPPED,
                sign_consumed=True
            )
        elif state.sign_id == SignType.LEFT:
            return ActionCommand(
                steering_angle=-MAX_STEERING,
                speed=MIN_SPEED,
                direction=1,
                new_state=SystemState.TURNING,
                sign_consumed=True
            )
        elif state.sign_id == SignType.RIGHT:
            return ActionCommand(
                steering_angle=MAX_STEERING,
                speed=MIN_SPEED,
                direction=1,
                new_state=SystemState.TURNING,
                sign_consumed=True
            )
        return ActionCommand(speed=BASE_SPEED, direction=1)

    def _lane_follow(self, state: SensorState) -> ActionCommand:
        """PID-based lane centering."""
        steering = self.pid.compute(setpoint=0.0, measured=state.lane_offset)
        steering = max(-MAX_STEERING, min(MAX_STEERING, steering))

        # Slow down in curves
        speed = BASE_SPEED
        if abs(state.lane_curvature) > 0.01:
            speed = max(MIN_SPEED, BASE_SPEED - abs(steering) * 0.5)

        return ActionCommand(
            steering_angle=steering,
            speed=speed,
            direction=1,
            new_state=SystemState.DRIVING
        )

    def reset(self) -> None:
        self.pid.reset()
        self._turn_start_time = 0.0
        self._stop_start_time = 0.0
```

---

## 6. PID Controller

### 6.1 What Is PID?
A **Proportional-Integral-Derivative** controller that smoothly corrects the car's steering based on how far off-center it is from the lane.

- **P** (Proportional): Corrects based on *current* error. Big offset → big correction.
- **I** (Integral): Corrects based on *accumulated* error over time. Fixes persistent drift.
- **D** (Derivative): Corrects based on *rate of change* of error. Prevents overshoot/oscillation.

### 6.2 `brain/pid.py`

```python
"""
brain/pid.py — Discrete PID Controller.

Used by the Brain to convert lane_offset into a smooth steering angle.
"""

import time


class PIDController:
    """
    A simple discrete PID controller.
    
    Usage:
        pid = PIDController(kp=0.8, ki=0.01, kd=0.3)
        steering = pid.compute(setpoint=0.0, measured=lane_offset)
    """

    def __init__(self, kp: float, ki: float, kd: float,
                 integral_limit: float = 100.0):
        """
        Args:
            kp: Proportional gain. Start with 0.5–1.0.
            ki: Integral gain. Start with 0.0–0.05. Too high = oscillation.
            kd: Derivative gain. Start with 0.1–0.5. Dampens overshoot.
            integral_limit: Clamp to prevent integral windup.
        """
        # TODO: Store gains and initialize internal state:
        #   self._prev_error, self._integral, self._prev_time

    def compute(self, setpoint: float, measured: float) -> float:
        """
        Compute PID output.
        
        Args:
            setpoint: Desired value (0.0 = perfectly centered).
            measured: Current measured value (lane_offset in pixels).
            
        Returns:
            Control output (steering angle correction).
        """
        # TODO: Implement P + I + D terms:
        #   1. Calculate dt from time.monotonic()
        #   2. error = setpoint - measured
        #   3. P term = kp * error
        #   4. I term = ki * accumulated_error (clamp with integral_limit!)
        #   5. D term = kd * (error - prev_error) / dt
        #   6. Update prev_error, prev_time
        #   7. Return p + i + d
        raise NotImplementedError

    def reset(self) -> None:
        """Reset accumulated state. Call when switching modes."""
        # TODO: Zero out _prev_error, _integral, reset _prev_time
        raise NotImplementedError
```

### 6.3 PID Tuning Guide

| Symptom | Fix |
|---|---|
| Car weaves side to side continuously | Reduce `kp` |
| Car drifts to one side over time | Increase `ki` slightly |
| Car oscillates wildly, overshoots corrections | Reduce `ki`, increase `kd` |
| Car reacts too slowly to curves | Increase `kp` |
| Car jerks at high speed | Increase `kd` |

**Tuning procedure**: Start with `ki=0, kd=0`. Increase `kp` until the car follows the lane but oscillates. Then increase `kd` until oscillation stops. Finally add a tiny `ki` if there's steady-state drift.

---

## 7. Subsystem Implementation Guides

### 7.1 Process 1 — Lane Detection (`vision/lane_detector.py`)

**Owner**: Runs on Core 0. Writes to `lane_offset`, `lane_curvature`, `lane_detected`.

**Algorithm — Classic OpenCV Pipeline**:

```
Camera Frame (640×480)
    │
    ▼
Crop to Bottom Half (Region of Interest)
    │
    ▼
Convert to Grayscale (or HSV for colored lanes)
    │
    ▼
Gaussian Blur (5×5 kernel) — reduce noise
    │
    ▼
Canny Edge Detection (threshold: 50–150)
    │
    ▼
Hough Line Transform (HoughLinesP)
    │
    ▼
Classify lines as LEFT lane / RIGHT lane
(by slope: negative slope = left, positive = right)
    │
    ▼
Calculate lane center = midpoint of left and right lane
    │
    ▼
lane_offset = image_center_x - lane_center_x
(negative = car is left of center, positive = right)
    │
    ▼
lane_curvature = estimated from slope difference
    │
    ▼
Write to shared memory
```

**Key implementation notes**:
- **ROI masking**: Only process the bottom 50-60% of the frame. The sky/walls are irrelevant.
- **Color filtering**: If lanes are a specific color (white/yellow tape), use HSV thresholding *before* Canny for much better results.
- **Sliding window** (advanced): For curved lanes, use a sliding window polynomial fit instead of Hough lines.
- **Frame rate**: This pipeline should run at 30+ FPS on Pi 4. If it doesn't, reduce resolution to 320×240.

**Process function signature**:

```python
def lane_detection_process(
    lane_offset: Value,       # c_double — write
    lane_curvature: Value,    # c_double — write
    lane_detected: Value,     # c_bool — write
    system_running: Value,    # c_bool — read (kill switch)
    shm_name: str,            # SharedMemory name for frame sharing with P2
    frame_lock: Lock,         # synchronize frame buffer access
    frame_width: int,
    frame_height: int,
) -> None:
    """
    Main loop for the lane detection process.
    Captures camera frames, runs OpenCV pipeline, writes results to shared memory.
    """
    import cv2
    import numpy as np
    from multiprocessing import shared_memory

    # Attach to the shared memory block created by main.py
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)

    while system_running.value:
        ret, frame = cap.read()
        if not ret:
            continue

        # Share frame with P2 via SharedMemory (~0.5ms zero-copy)
        with frame_lock:
            np.copyto(shared_frame, frame)

        # --- YOUR OpenCV pipeline here ---
        # offset, curvature, detected = run_pipeline(frame)

        # Write results atomically
        # lane_offset.value = offset
        # lane_curvature.value = curvature
        # lane_detected.value = detected

    cap.release()
    shm.close()  # Detach from shared memory (main.py owns unlink)
```

---

### 7.2 Process 2 — Sign Detection (`vision/sign_detector.py`)

**Owner**: Runs on Core 1. Writes to `sign_id`, `sign_confidence`.

**Model Choice — YOLOv8n / YOLO11n (Nano)**:
- Train on **your actual track signs** under the **actual room lighting**.
- Export to **NCNN** format for best Pi 4 CPU performance:
  ```bash
  yolo export model=best.pt format=ncnn imgsz=320
  ```
- Expected inference: ~15–20 FPS at 320×320 on Pi 4 with NCNN.

**Alternative — Lightweight classifier (no YOLO needed)**:
Since you only have 3 sign classes on a controlled track:
1. Color-filter the frame (red for stop, blue/green for directional arrows)
2. Find contours → bounding box
3. Crop and classify with a tiny MobileNetV2 or even template matching
4. Runs at 30+ FPS, simpler to debug

**Dataset preparation**:
- Take 200+ photos of each sign from the car's camera perspective
- Include various distances (close, medium, far)
- Include slight angles and lighting variations
- Use Roboflow or LabelImg for annotation
- Augment: rotation ±15°, brightness ±20%, blur

**Process function signature**:

```python
def sign_detection_process(
    sign_id: Value,           # c_int — write (SignType enum)
    sign_confidence: Value,   # c_double — write
    system_running: Value,    # c_bool — read
    shm_name: str,            # SharedMemory name — read frames from P1
    frame_lock: Lock,         # synchronize
    frame_width: int,
    frame_height: int,
) -> None:
    """
    Main loop for sign detection process.
    Reads frames from shared buffer, runs YOLO/classifier, writes results.
    """
    import numpy as np
    from multiprocessing import shared_memory

    # Attach to the shared memory block (created by main.py, written by P1)
    shm = shared_memory.SharedMemory(name=shm_name)
    shared_frame = np.ndarray(
        (frame_height, frame_width, 3), dtype=np.uint8, buffer=shm.buf
    )

    # Load model ONCE at startup
    # from ultralytics import YOLO
    # model = YOLO("best_ncnn_model", task="detect")

    while system_running.value:
        # Snapshot the latest frame (~0.5ms zero-copy read)
        with frame_lock:
            frame = shared_frame.copy()

        # --- YOUR inference here ---
        # results = model.predict(frame, imgsz=320, conf=0.5)

        # Parse best detection
        # if results and len(results[0].boxes) > 0:
        #     best = results[0].boxes[0]
        #     sign_id.value = int(best.cls)
        #     sign_confidence.value = float(best.conf)
        # else:
        #     sign_id.value = SignType.NONE
        #     sign_confidence.value = 0.0

    shm.close()  # Detach from shared memory (main.py owns unlink)
```

> [!TIP]
> **Sign persistence**: Don't reset `sign_id` to NONE every frame. Let the Orchestrator reset it via `sign_consumed=True` in the ActionCommand. This prevents the car from "forgetting" a sign between frames.

> [!WARNING]
> **Race condition**: P2 writes `sign_id` continuously while the Orchestrator resets it via `sign_consumed`. If P2 writes a new detection between the Brain's decision and the reset, that detection is silently dropped. At 30Hz this is rare, but for extra safety you could add a `sign_generation: Value(c_int)` counter that P2 increments on every new detection — the Orchestrator only resets if the generation hasn't changed.

---

### 7.3 Process 3 — Voice & Ultrasonic (`sensors/`)

**Owner**: Runs on Core 2. Writes to `voice_command`, `obstacle_dist`.

#### 7.3.1 Voice Commands (`sensors/voice.py`)

**Library**: **Vosk** (offline, ~50MB model, runs on Pi 4 CPU).

```bash
pip install vosk sounddevice
# Download small English model:
# https://alphacephei.com/vosk/models → vosk-model-small-en-us-0.15 (~40MB)
```

**Implementation approach**:
```python
import vosk
import sounddevice as sd
import json

model = vosk.Model("vosk-model-small-en-us-0.15")
recognizer = vosk.KaldiRecognizer(model, 16000)

# Keywords to detect
KEYWORDS = {
    "start": VoiceCommand.START,
    "stop": VoiceCommand.STOP,
    "pause": VoiceCommand.PAUSE,
    "continue": VoiceCommand.CONTINUE,
}

def voice_listener(voice_command: Value, system_running: Value):
    with sd.RawInputStream(samplerate=16000, blocksize=4000,
                           dtype="int16", channels=1) as stream:
        while system_running.value:
            data = stream.read(4000)[0]
            if recognizer.AcceptWaveform(bytes(data)):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()
                for keyword, cmd in KEYWORDS.items():
                    if keyword in text:
                        voice_command.value = cmd
                        break
```

#### 7.3.2 Ultrasonic Sensor (`sensors/ultrasonic.py`)

```python
def ultrasonic_reader(obstacle_dist: Value, system_running: Value):
    """
    Read HC-SR04 ultrasonic sensor at ~10 Hz.
    Uses picarx built-in ultrasonic if available, or raw GPIO.
    """
    from picarx import Picarx
    import time

    px = Picarx()
    while system_running.value:
        try:
            dist = px.ultrasonic.read()
            if dist is not None and dist > 0:
                obstacle_dist.value = dist
        except Exception:
            pass
        time.sleep(0.1)  # 10 Hz
```

> [!WARNING]
> **Picarx in P3**: If the ultrasonic sensor is accessed via `picarx`, creating a second `Picarx()` instance in P3 may conflict with P4's instance (I²C bus). **Preferred solution**: Read the ultrasonic sensor directly via GPIO in P3, or move ultrasonic reading to P4's main loop (it's cheap enough at 10Hz).

---

### 7.4 Process 4 — Orchestrator (`main.py`)

**Owner**: Runs on Core 3. The ONLY process that touches `picarx` hardware.

```python
"""
main.py — Orchestrator process.

Spawns all worker processes, runs the 30Hz control loop,
and is the ONLY process that sends commands to the PiCar-X hardware.
"""

import time
import multiprocessing as mp
from multiprocessing import shared_memory
from ctypes import c_double, c_bool, c_int

from contracts import SensorState, ActionCommand, SystemState
from brain.subsumption import SubsumptionBrain
from vision.lane_detector import lane_detection_process
from vision.sign_detector import sign_detection_process
from sensors.voice import voice_listener
from sensors.ultrasonic import ultrasonic_reader


TICK_RATE = 30  # Hz
TICK_INTERVAL = 1.0 / TICK_RATE


def main():
    # ── Shared Memory ──────────────────────────────────────
    lane_offset     = mp.Value(c_double, 0.0)
    lane_curvature  = mp.Value(c_double, 0.0)
    lane_detected   = mp.Value(c_bool, False)
    sign_id         = mp.Value(c_int, 0)
    sign_confidence = mp.Value(c_double, 0.0)
    obstacle_dist   = mp.Value(c_double, 999.0)
    voice_command   = mp.Value(c_int, 0)
    system_running  = mp.Value(c_bool, True)

    # Frame sharing via SharedMemory (zero-copy numpy, ~0.5ms vs ~100ms with Array)
    FRAME_W, FRAME_H = 640, 480
    shm = shared_memory.SharedMemory(create=True, size=FRAME_W * FRAME_H * 3)
    frame_lock = mp.Lock()

    # ── Spawn Worker Processes ─────────────────────────────
    workers = [
        mp.Process(
            target=lane_detection_process,
            args=(lane_offset, lane_curvature, lane_detected,
                  system_running, shm.name, frame_lock, FRAME_W, FRAME_H),
            daemon=True, name="P1-LaneDetect"
        ),
        mp.Process(
            target=sign_detection_process,
            args=(sign_id, sign_confidence, system_running,
                  shm.name, frame_lock, FRAME_W, FRAME_H),
            daemon=True, name="P2-SignDetect"
        ),
        mp.Process(
            target=voice_listener,
            args=(voice_command, system_running),
            daemon=True, name="P3-Voice"
        ),
        # Note: ultrasonic handled in main loop or separate thread
    ]

    for w in workers:
        w.start()

    # ── Initialize Hardware & Brain ────────────────────────
    from picarx import Picarx
    px = Picarx()
    brain = SubsumptionBrain()
    current_state = SystemState.IDLE
    current_speed = 0.0
    current_steering = 0.0
    last_ultrasonic_read = 0.0  # Throttle ultrasonic to ~10Hz

    print("[Orchestrator] All systems GO. Waiting for START command...")

    try:
        while system_running.value:
            tick_start = time.monotonic()

            # 1. Read ultrasonic (~10Hz — each read can block up to 30ms,
            #    so don't call every tick or it eats the 33ms budget)
            now = time.monotonic()
            if now - last_ultrasonic_read >= 0.1:  # 10Hz
                try:
                    dist = px.ultrasonic.read()
                    if dist is not None and dist > 0:
                        obstacle_dist.value = dist
                except Exception:
                    pass
                last_ultrasonic_read = now

            # 2. Build SensorState DTO from shared memory
            state = SensorState(
                lane_offset=lane_offset.value,
                lane_curvature=lane_curvature.value,
                lane_detected=lane_detected.value,
                sign_id=sign_id.value,
                sign_confidence=sign_confidence.value,
                obstacle_dist_cm=obstacle_dist.value,
                voice_command=voice_command.value,
                current_state=current_state,
                speed=current_speed,
                steering_angle=current_steering,
            )

            # 3. Brain decides
            action: ActionCommand = brain.decide_next_action(state)

            # 4. Execute ActionCommand on hardware
            px.set_dir_servo_angle(action.steering_angle)
            if action.direction == 1:
                px.forward(action.speed)
            elif action.direction == -1:
                px.backward(action.speed)
            else:
                px.stop()

            # 5. Update state
            current_state = action.new_state
            current_speed = action.speed
            current_steering = action.steering_angle

            # 6. Consume acknowledged signals
            if action.sign_consumed:
                sign_id.value = 0
                sign_confidence.value = 0.0
            if action.voice_consumed:
                voice_command.value = 0

            # 7. Sleep to maintain tick rate
            elapsed = time.monotonic() - tick_start
            sleep_time = TICK_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[Orchestrator] Shutdown requested.")
    finally:
        system_running.value = False
        px.stop()
        px.set_dir_servo_angle(0)
        for w in workers:
            w.join(timeout=2.0)
        shm.close()
        shm.unlink()  # Free the shared memory block (only the creator calls unlink)
        print("[Orchestrator] All processes terminated. Goodbye.")


if __name__ == "__main__":
    main()
```

---

## 8. File / Directory Structure

```
picar-x-autonomous/
│
├── main.py                      # P4: Orchestrator (ONLY hardware access)
├── contracts.py                 # DTOs: SensorState, ActionCommand, Enums
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
│
├── brain/
│   ├── __init__.py
│   ├── interface.py             # AutonomousBrain ABC
│   ├── subsumption.py           # SubsumptionBrain implementation
│   └── pid.py                   # PID controller
│
├── vision/
│   ├── __init__.py
│   ├── lane_detector.py         # P1: OpenCV lane detection process
│   └── sign_detector.py         # P2: YOLO/classifier sign detection process
│
├── sensors/
│   ├── __init__.py
│   ├── voice.py                 # P3a: Vosk voice command listener
│   └── ultrasonic.py            # P3b: HC-SR04 ultrasonic reader
│
├── models/
│   ├── yolo/                    # Trained YOLO model files
│   │   ├── best.pt              # PyTorch weights
│   │   └── best_ncnn_model/     # NCNN exported model
│   └── vosk/                    # Vosk speech model
│       └── vosk-model-small-en-us-0.15/
│
├── config/
│   └── settings.py              # All tunable constants in one place
│
├── utils/
│   ├── __init__.py
│   └── logger.py                # Shared logging utilities
│
├── tests/
│   ├── test_brain.py            # Unit tests for brain logic
│   ├── test_pid.py              # Unit tests for PID controller
│   └── test_contracts.py        # DTO validation tests
│
└── scripts/
    ├── train_yolo.py            # YOLO training script
    ├── collect_data.py          # Camera data collection for training
    └── calibrate_pid.py         # Interactive PID tuning helper
```

---

## 9. Dependencies

### 9.1 `requirements.txt`

```
# Core
picarx                  # SunFounder PiCar-X library
opencv-python-headless  # OpenCV without GUI (lighter for Pi)
numpy                   # Array operations

# Sign Detection (choose one)
ultralytics             # YOLOv8/YOLO11 (includes NCNN export)
# OR
tflite-runtime          # If using TFLite instead of NCNN

# Voice Commands
vosk                    # Offline speech recognition
sounddevice             # Microphone input

# Utilities
Pillow                  # Image handling
```

### 9.2 Installation on Pi 4

```bash
# System dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv libatlas-base-dev \
    portaudio19-dev libopencv-dev

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

```

---

## 10. Testing Strategy

### 10.1 Off-Pi Testing (Laptops)
The Brain and PID are **pure logic** — no hardware dependency. Test them anywhere:

```python
# test_brain.py
from contracts import SensorState, SignType, SystemState
from brain.subsumption import SubsumptionBrain

def test_stop_sign_halts_car():
    brain = SubsumptionBrain()
    state = SensorState(
        sign_id=SignType.STOP,
        sign_confidence=0.9,
        lane_detected=True,
        current_state=SystemState.DRIVING,
    )
    action = brain.decide_next_action(state)
    assert action.speed == 0
    assert action.new_state == SystemState.STOPPED

def test_obstacle_overrides_lane_following():
    brain = SubsumptionBrain()
    state = SensorState(
        obstacle_dist_cm=15.0,  # Very close!
        lane_detected=True,
        lane_offset=10.0,
        current_state=SystemState.DRIVING,
    )
    action = brain.decide_next_action(state)
    assert action.speed == 0  # Must stop, not follow lane

def test_voice_stop_overrides_everything():
    brain = SubsumptionBrain()
    state = SensorState(
        voice_command=2,  # VoiceCommand.STOP
        sign_id=SignType.LEFT,
        sign_confidence=0.95,
        lane_detected=True,
        current_state=SystemState.DRIVING,
    )
    action = brain.decide_next_action(state)
    assert action.speed == 0
    assert action.new_state == SystemState.STOPPED
```

### 10.2 On-Pi Integration Testing
1. Run `main.py` with the car on blocks (wheels off ground)
2. Hold signs in front of the camera
3. Observe motor/servo reactions
4. Use `print()` or a shared log file to trace SensorState → ActionCommand flow

### 10.3 Track Testing
1. Start with lane following only (disable sign detection)
2. Tune PID until the car completes a lap smoothly
3. Enable sign detection and test each sign individually
4. Full integration run

---

## 12. Appendix: Key Constants Reference

All tunable constants should live in `config/settings.py` so they can be changed without modifying logic code:

```python
"""config/settings.py — All tunable parameters in one place."""

# ── Camera ──
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CAMERA_INDEX = 0

# ── Lane Detection ──
ROI_TOP_PERCENT = 0.5          # Crop top 50% of frame
CANNY_LOW = 50
CANNY_HIGH = 150
HOUGH_THRESHOLD = 50
HOUGH_MIN_LINE_LENGTH = 50
HOUGH_MAX_LINE_GAP = 150

# ── Sign Detection ──
YOLO_INPUT_SIZE = 320
SIGN_CONFIDENCE_THRESHOLD = 0.6
SIGN_MODEL_PATH = "models/yolo/best_ncnn_model"

# ── PID ──
PID_KP = 0.8
PID_KI = 0.01
PID_KD = 0.3

# ── Driving ──
BASE_SPEED = 30
MIN_SPEED = 15
MAX_SPEED = 50
MAX_STEERING_ANGLE = 30        # degrees
FALLBACK_SPEED = 15

# ── Obstacle ──
OBSTACLE_STOP_CM = 25.0
OBSTACLE_SLOW_CM = 50.0

# ── Timing ──
TICK_RATE_HZ = 30
STOP_SIGN_WAIT_SEC = 3.0
TURN_DURATION_SEC = 2.0

# ── Voice ──
VOSK_MODEL_PATH = "models/vosk/vosk-model-small-en-us-0.15"
VOICE_SAMPLE_RATE = 16000
```

---

> [!IMPORTANT]
> **Golden Rule for all team members**: Your process writes to shared memory. The Orchestrator reads it. The Brain decides. The Orchestrator acts. **Never skip a layer.**

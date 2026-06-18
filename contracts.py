"""
contracts.py — Data Transfer Objects for inter-process communication.

These dataclasses define the ONLY data structures that cross process
boundaries. All fields map 1:1 to multiprocessing.Value shared memory.

DO NOT import picarx, OpenCV, or any heavy library here.
"""

from dataclasses import dataclass
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

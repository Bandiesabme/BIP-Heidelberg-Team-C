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

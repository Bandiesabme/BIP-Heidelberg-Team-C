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

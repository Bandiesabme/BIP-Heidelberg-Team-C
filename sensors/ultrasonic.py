"""
sensors/ultrasonic.py — Ultrasonic distance sensor reader.

NOTE: The ultrasonic sensor is currently read directly in the Orchestrator
(main.py) at ~10Hz to avoid I²C bus conflicts from a separate Picarx instance.

This module is provided as a fallback if you need to read via raw GPIO instead.
"""

from multiprocessing import Value


def ultrasonic_reader(obstacle_dist: Value, system_running: Value) -> None:
    """
    Read HC-SR04 ultrasonic sensor at ~10 Hz via raw GPIO.

    WARNING: Do NOT create a second Picarx() instance here —
    it will conflict with the Orchestrator's I²C bus access.
    Use raw GPIO or move reading to main.py's loop (current approach).
    """
    # TODO: Implement raw GPIO ultrasonic reading if needed:
    #   1. Configure trigger and echo GPIO pins
    #   2. In loop while system_running.value:
    #      a. Send 10µs pulse on trigger pin
    #      b. Measure echo pulse duration
    #      c. distance_cm = duration * 17150  (speed of sound / 2)
    #      d. obstacle_dist.value = distance_cm
    #      e. time.sleep(0.1)  # 10Hz
    raise NotImplementedError

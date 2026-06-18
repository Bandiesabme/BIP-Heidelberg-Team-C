"""
tests/test_pid.py — Unit tests for the PID controller.

These tests run on any machine (no Pi hardware needed).
"""

# TODO: Add tests once PID is implemented:
#
# from brain.pid import PIDController
#
# def test_zero_error_returns_zero():
#     pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
#     output = pid.compute(setpoint=0.0, measured=0.0)
#     assert output == 0.0
#
# def test_proportional_response():
#     pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
#     output = pid.compute(setpoint=0.0, measured=10.0)
#     assert output < 0  # Should steer opposite to error
#
# def test_integral_windup_clamped():
#     pid = PIDController(kp=0.0, ki=1.0, kd=0.0, integral_limit=50.0)
#     for _ in range(1000):
#         pid.compute(setpoint=0.0, measured=100.0)
#     # Integral should be clamped, not blow up
#
# def test_reset_clears_state():
#     pid = PIDController(kp=1.0, ki=0.1, kd=0.1)
#     pid.compute(setpoint=0.0, measured=50.0)
#     pid.reset()
#     # After reset, internal state should be zeroed

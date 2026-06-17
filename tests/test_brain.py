"""
tests/test_brain.py — Unit tests for the subsumption brain.

These tests run on any machine (no Pi hardware needed).
"""

from contracts import SensorState, ActionCommand, SignType, VoiceCommand, SystemState
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
        voice_command=VoiceCommand.STOP,
        sign_id=SignType.LEFT,
        sign_confidence=0.95,
        lane_detected=True,
        current_state=SystemState.DRIVING,
    )
    action = brain.decide_next_action(state)
    assert action.speed == 0
    assert action.new_state == SystemState.STOPPED


def test_idle_state_does_not_move():
    brain = SubsumptionBrain()
    state = SensorState(
        current_state=SystemState.IDLE,
        lane_detected=True,
    )
    action = brain.decide_next_action(state)
    assert action.speed == 0


def test_fallback_when_no_lane_detected():
    brain = SubsumptionBrain()
    state = SensorState(
        lane_detected=False,
        current_state=SystemState.DRIVING,
    )
    action = brain.decide_next_action(state)
    assert action.speed > 0
    assert action.steering_angle == 0.0

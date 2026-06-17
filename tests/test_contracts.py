"""
tests/test_contracts.py — DTO validation tests.

Ensures contracts remain immutable and correctly typed.
"""

from contracts import (
    SensorState, ActionCommand,
    SignType, VoiceCommand, SystemState
)


def test_sensor_state_is_frozen():
    state = SensorState()
    try:
        state.lane_offset = 99.0  # type: ignore
        assert False, "SensorState should be frozen (immutable)"
    except AttributeError:
        pass  # Expected


def test_action_command_is_frozen():
    action = ActionCommand()
    try:
        action.speed = 99.0  # type: ignore
        assert False, "ActionCommand should be frozen (immutable)"
    except AttributeError:
        pass  # Expected


def test_sign_type_enum_values():
    assert SignType.NONE == 0
    assert SignType.LEFT == 1
    assert SignType.RIGHT == 2
    assert SignType.STOP == 3


def test_voice_command_enum_values():
    assert VoiceCommand.NONE == 0
    assert VoiceCommand.START == 1
    assert VoiceCommand.STOP == 2
    assert VoiceCommand.PAUSE == 3
    assert VoiceCommand.CONTINUE == 4


def test_system_state_enum_values():
    assert SystemState.IDLE == 0
    assert SystemState.DRIVING == 1
    assert SystemState.TURNING == 2
    assert SystemState.STOPPED == 3
    assert SystemState.PAUSED == 4
    assert SystemState.AVOIDING == 5


def test_sensor_state_defaults():
    state = SensorState()
    assert state.lane_offset == 0.0
    assert state.lane_detected is False
    assert state.obstacle_dist_cm == 999.0
    assert state.current_state == SystemState.IDLE


def test_action_command_defaults():
    action = ActionCommand()
    assert action.steering_angle == 0.0
    assert action.speed == 0.0
    assert action.direction == 1
    assert action.new_state == SystemState.DRIVING
    assert action.sign_consumed is False
    assert action.voice_consumed is False

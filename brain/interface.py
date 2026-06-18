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

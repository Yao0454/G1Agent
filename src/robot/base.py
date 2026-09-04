"""Hardware-independent robot operations required by V0.1 skills."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RobotState:
    hardware: bool
    connected: bool
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionVerification:
    completed: bool
    observable: bool
    message: str
    details: dict[str, object] = field(default_factory=dict)


class RobotCommandError(RuntimeError):
    """Raised when the robot API rejects or fails a command."""


class RobotAdapter(Protocol):
    async def get_state(self) -> RobotState: ...

    async def stop(self) -> None:
        """Request the adapter's defined software stop; not a physical e-stop."""
        ...

    async def wave(self, arm: str) -> None: ...

    async def wait_for_wave_completion(
        self,
        arm: str,
        timeout_s: float,
    ) -> ActionVerification: ...

    async def execute_arm_action(
        self,
        action_id: int,
        action_name: str,
    ) -> None: ...

    async def wait_for_arm_action_completion(
        self,
        action_id: int,
        action_name: str,
        timeout_s: float,
    ) -> ActionVerification: ...

    async def release_arm(self) -> None: ...

    async def execute_loco_action(
        self,
        action: str,
        arguments: Mapping[str, object] | None = None,
    ) -> None: ...

    async def move_velocity(
        self,
        forward_m_s: float,
        lateral_m_s: float,
        yaw_rad_s: float,
    ) -> None: ...

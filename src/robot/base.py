"""Hardware-independent robot operations required by V0.1 skills."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RobotState:
    hardware: bool
    connected: bool
    details: dict[str, object] = field(default_factory=dict)


class RobotCommandError(RuntimeError):
    """Raised when the robot API rejects or fails a command."""


class RobotAdapter(Protocol):
    async def get_state(self) -> RobotState: ...

    async def stop(self) -> None:
        """Request the adapter's defined software stop; not a physical e-stop."""
        ...

    async def wave(self, arm: str) -> None: ...

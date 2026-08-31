"""In-process robot adapter for Agent and tool development without hardware."""

from .base import RobotState


class SimulatedRobotAdapter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []

    async def get_state(self) -> RobotState:
        return RobotState(hardware=False, connected=True)

    async def stop(self) -> None:
        self.events.append(("stop", None))

    async def wave(self, arm: str) -> None:
        self.events.append(("wave", arm))

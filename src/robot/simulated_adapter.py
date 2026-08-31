"""In-process robot adapter for Agent and tool development without hardware."""

from .base import RobotState


class SimulatedRobotAdapter:
    def __init__(self) -> None:
        self.events: list[tuple[str, object | None]] = []

    async def get_state(self) -> RobotState:
        return RobotState(hardware=False, connected=True)

    async def stop(self) -> None:
        self.events.append(("stop", None))

    async def wave(self, arm: str) -> None:
        self.events.append(("wave", arm))

    async def move_velocity(
        self,
        forward_m_s: float,
        lateral_m_s: float,
        yaw_rad_s: float,
    ) -> None:
        self.events.append(
            (
                "move_velocity",
                (forward_m_s, lateral_m_s, yaw_rad_s),
            )
        )

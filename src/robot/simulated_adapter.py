"""In-process robot adapter for Agent and tool development without hardware."""

from collections.abc import Mapping

from .base import ActionVerification, RobotState


class SimulatedRobotAdapter:
    def __init__(self) -> None:
        self.events: list[tuple[str, object | None]] = []

    async def get_state(self) -> RobotState:
        return RobotState(hardware=False, connected=True)

    async def stop(self) -> None:
        self.events.append(("stop", None))

    async def wave(self, arm: str) -> None:
        self.events.append(("wave", arm))

    async def wait_for_wave_completion(
        self,
        arm: str,
        timeout_s: float,
    ) -> ActionVerification:
        return ActionVerification(
            completed=True,
            observable=True,
            message="simulated wave completed",
            details={"arm": arm, "method": "simulation"},
        )

    async def execute_arm_action(
        self,
        action_id: int,
        action_name: str,
    ) -> None:
        self.events.append(
            (
                "arm_action",
                {"action_id": action_id, "action_name": action_name},
            )
        )

    async def wait_for_arm_action_completion(
        self,
        action_id: int,
        action_name: str,
        timeout_s: float,
    ) -> ActionVerification:
        return ActionVerification(
            completed=True,
            observable=True,
            message=f"simulated {action_name} completed",
            details={
                "method": "simulation",
                "action_id": action_id,
                "action_name": action_name,
                "action_observed": True,
            },
        )

    async def release_arm(self) -> None:
        self.events.append(("release_arm", None))

    async def execute_loco_action(
        self,
        action: str,
        arguments: Mapping[str, object] | None = None,
    ) -> None:
        self.events.append(("loco_action", (action, dict(arguments or {}))))

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

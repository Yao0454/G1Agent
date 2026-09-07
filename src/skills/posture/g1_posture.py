"""G1 high-level posture skills exposed by LocoClient."""

from __future__ import annotations

from dataclasses import dataclass

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill


class PostureArgs(SkillArgs):
    pass


@dataclass(frozen=True, slots=True)
class PostureSpec:
    skill_name: str
    sdk_action: str
    description: str
    operator_only: bool = False
    dangerous: bool = False


POSTURE_SPECS = (
    PostureSpec("squat", "squat", "Enter the G1 squat posture."),
    PostureSpec("sit", "sit", "Enter the G1 sitting posture."),
    PostureSpec("stand_up", "stand_up", "Stand up using the G1 controller."),
    PostureSpec("high_stand", "high_stand", "Use the high standing height."),
    PostureSpec("low_stand", "low_stand", "Use the low standing height."),
    PostureSpec(
        "balance_stand",
        "balance_stand",
        "Enter balanced standing mode.",
    ),
    PostureSpec(
        "start",
        "start",
        "Switch the G1 controller to FSM 500.",
        operator_only=True,
    ),
    PostureSpec(
        "damp",
        "damp",
        "Switch the G1 controller to damping mode.",
        operator_only=True,
        dangerous=True,
    ),
    PostureSpec(
        "zero_torque",
        "zero_torque",
        "Disable commanded joint torque through FSM 0.",
        operator_only=True,
        dangerous=True,
    ),
)


class PostureSkill(RobotSkill[PostureArgs]):
    args_model = PostureArgs

    def __init__(self, spec: PostureSpec) -> None:
        self.spec = spec
        tags = ["posture", "sdk_loco"]
        if spec.operator_only:
            tags.append("operator_only")
        if spec.dangerous:
            tags.append("dangerous")
        self.metadata = SkillMetadata(
            name=spec.skill_name,
            description=spec.description,
            tags=tuple(tags),
            required_resources=("mobile_base",),
            timeout_s=12.0,
            interruptible=not spec.dangerous,
        )

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: PostureArgs,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""

    async def execute(
        self,
        ctx: SkillContext,
        args: PostureArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action(self.spec.sdk_action)
        return SkillResult.ok(
            f"{self.spec.sdk_action} command accepted",
            sdk_action=self.spec.sdk_action,
        )


def build_posture_skills(
    *,
    operator_only: bool,
) -> tuple[PostureSkill, ...]:
    return tuple(
        PostureSkill(spec)
        for spec in POSTURE_SPECS
        if spec.operator_only is operator_only
    )


__all__ = [
    "POSTURE_SPECS",
    "PostureArgs",
    "PostureSkill",
    "PostureSpec",
    "build_posture_skills",
]

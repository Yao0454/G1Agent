"""Right-hand waving skill backed by the robot adapter."""

from typing import Literal

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill


class WaveArgs(SkillArgs):
    arm: Literal["right"] = "right"


class WaveSkill(RobotSkill[WaveArgs]):
    metadata = SkillMetadata(
        name="wave",
        description="Wave the robot's right hand as a social gesture.",
        tags=("gesture", "social"),
        required_resources=("right_arm",),
        timeout_s=10.0,
    )
    args_model = WaveArgs

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: WaveArgs,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""

    async def execute(self, ctx: SkillContext, args: WaveArgs) -> SkillResult:
        await ctx.robot.wave(args.arm)
        return SkillResult.ok("wave completed", arm=args.arm)

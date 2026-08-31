"""Bounded open-loop backward movement with a mandatory software stop."""

import asyncio

from pydantic import Field

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill


class MoveBackwardArgs(SkillArgs):
    distance_m: float = Field(default=0.2, ge=0.05, le=0.3)


class MoveBackwardSkill(RobotSkill[MoveBackwardArgs]):
    metadata = SkillMetadata(
        name="move_backward",
        description="Move backward by a short bounded distance, then stop.",
        tags=("motion", "safety"),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    args_model = MoveBackwardArgs

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: MoveBackwardArgs,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""

    async def execute(
        self,
        ctx: SkillContext,
        args: MoveBackwardArgs,
    ) -> SkillResult:
        speed_m_s = max(args.distance_m, 0.1)
        duration_s = args.distance_m / speed_m_s
        ctx.runtime_data["motion_attempted"] = True
        await ctx.robot.move_velocity(-speed_m_s, 0.0, 0.0)
        await asyncio.sleep(duration_s)
        await ctx.robot.stop()
        ctx.runtime_data["motion_stopped"] = True
        return SkillResult.ok(
            "backward movement completed",
            distance_m=args.distance_m,
            speed_m_s=speed_m_s,
        )

    async def cleanup(self, ctx: SkillContext, args: MoveBackwardArgs) -> None:
        if (
            ctx.runtime_data.get("motion_attempted") is True
            and ctx.runtime_data.get("motion_stopped") is not True
        ):
            await ctx.robot.stop()

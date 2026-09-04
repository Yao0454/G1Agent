"""Right-hand waving skill backed by the robot adapter."""

from typing import Literal

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill
from core.types import FailureCode, SkillStatus

from .arm_actions import check_arm_action_preconditions

WAVE_VERIFICATION_TIMEOUT_S = 6.0


class WaveArgs(SkillArgs):
    arm: Literal["right"] = "right"


class WaveSkill(RobotSkill[WaveArgs]):
    metadata = SkillMetadata(
        name="wave",
        description="Wave the robot's right hand as a social gesture.",
        tags=("gesture", "social"),
        required_resources=("upper_body",),
        # The G1 action RPC can consume its 10 s client timeout before
        # post-action feedback is observed. Keep both phases inside this budget.
        timeout_s=20.0,
    )
    args_model = WaveArgs

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: WaveArgs,
    ) -> tuple[bool, str]:
        return await check_arm_action_preconditions(ctx)

    async def execute(self, ctx: SkillContext, args: WaveArgs) -> SkillResult:
        await ctx.robot.wave(args.arm)
        return SkillResult.ok(
            "wave command accepted",
            arm=args.arm,
            command_accepted=True,
        )

    async def verify(
        self,
        ctx: SkillContext,
        args: WaveArgs,
        result: SkillResult,
    ) -> SkillResult:
        verification = await ctx.robot.wait_for_wave_completion(
            args.arm,
            timeout_s=WAVE_VERIFICATION_TIMEOUT_S,
        )
        details = {
            "observable": verification.observable,
            "completed": verification.completed,
            **verification.details,
        }
        if not verification.completed and not verification.observable:
            result.message = (
                "wave command accepted; completion feedback unavailable"
            )
            result.data["completion_verified"] = False
            result.verification = details
            return result
        if not verification.completed:
            failure = SkillResult.fail(
                SkillStatus.VERIFICATION_FAILED,
                verification.message,
                failure_code=FailureCode.VERIFICATION_FAILED,
                arm=args.arm,
                command_accepted=True,
            )
            failure.verification = details
            return failure

        result.message = verification.message
        result.data["completion_verified"] = True
        result.verification = details
        return result

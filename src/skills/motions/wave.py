"""Right-hand waving skill backed by the robot adapter."""

from typing import Literal

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill
from core.types import FailureCode, SkillStatus


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
        if state.hardware:
            fsm_id = state.details.get("fsm_id")
            if fsm_id not in {500, 501, 801}:
                return (
                    False,
                    (
                        f"G1 FSM {fsm_id!r} does not support arm actions; "
                        "enter a supported Sport mode first"
                    ),
                )
        return True, ""

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
            timeout_s=6.0,
        )
        details = {
            "observable": verification.observable,
            "completed": verification.completed,
            **verification.details,
        }
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
        result.verification = details
        return result

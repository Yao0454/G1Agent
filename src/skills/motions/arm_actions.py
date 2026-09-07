"""Unitree G1 built-in upper-body action skills."""

from __future__ import annotations

import asyncio

from pydantic import Field

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill
from core.types import FailureCode, SkillStatus
from robot import G1_ARM_ACTION_SPECS, G1ArmActionSpec

ARM_ACTION_VERIFICATION_TIMEOUT_S = 6.0
_ARM_ACTION_FSM_IDS = frozenset({500, 501, 801})


class ArmActionArgs(SkillArgs):
    pass


async def check_arm_action_preconditions(ctx: SkillContext) -> tuple[bool, str]:
    state = await ctx.robot.get_state()
    if state.hardware and not state.connected:
        return False, "robot is not connected"
    if not state.hardware:
        return True, ""

    fsm_id = state.details.get("fsm_id")
    if fsm_id not in _ARM_ACTION_FSM_IDS:
        return (
            False,
            (
                f"G1 FSM {fsm_id!r} does not support arm actions; "
                "enter a supported Sport mode first"
            ),
        )
    fsm_mode = state.details.get("fsm_mode")
    if fsm_id == 801 and fsm_mode is not None and fsm_mode not in {0, 3}:
        return (
            False,
            f"G1 FSM 801 mode {fsm_mode!r} does not support arm actions",
        )
    return True, ""


def apply_arm_action_verification(
    result: SkillResult,
    verification_message: str,
    *,
    completed: bool,
    observable: bool,
    details: dict[str, object],
    action_id: int,
    action_name: str,
) -> SkillResult:
    verification_payload = {
        "observable": observable,
        "completed": completed,
        **details,
    }
    if not completed and not observable:
        result.message = (
            f"{action_name} command accepted; completion feedback unavailable"
        )
        result.data["completion_verified"] = False
        result.verification = verification_payload
        return result
    if not completed:
        failure = SkillResult.fail(
            SkillStatus.VERIFICATION_FAILED,
            verification_message,
            failure_code=FailureCode.VERIFICATION_FAILED,
            action_id=action_id,
            action_name=action_name,
            command_accepted=True,
        )
        failure.verification = verification_payload
        return failure

    result.message = verification_message
    result.data["completion_verified"] = True
    result.verification = verification_payload
    return result


class PresetArmActionSkill(RobotSkill[ArmActionArgs]):
    args_model = ArmActionArgs

    def __init__(self, spec: G1ArmActionSpec) -> None:
        if spec.skill_name in {"wave", "handshake", "release_arm"}:
            raise ValueError(f"{spec.skill_name} has a dedicated skill implementation")
        self.spec = spec
        self.metadata = SkillMetadata(
            name=spec.skill_name,
            description=spec.description,
            tags=("gesture", "sdk_preset"),
            required_resources=("upper_body",),
            timeout_s=20.0,
        )

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: ArmActionArgs,
    ) -> tuple[bool, str]:
        return await check_arm_action_preconditions(ctx)

    async def execute(
        self,
        ctx: SkillContext,
        args: ArmActionArgs,
    ) -> SkillResult:
        await ctx.robot.execute_arm_action(
            self.spec.action_id,
            self.spec.sdk_name,
        )
        ctx.runtime_data["arm_action_started"] = True
        return SkillResult.ok(
            f"{self.spec.sdk_name} command accepted",
            action_id=self.spec.action_id,
            action_name=self.spec.sdk_name,
            command_accepted=True,
        )

    async def verify(
        self,
        ctx: SkillContext,
        args: ArmActionArgs,
        result: SkillResult,
    ) -> SkillResult:
        verification = await ctx.robot.wait_for_arm_action_completion(
            self.spec.action_id,
            self.spec.sdk_name,
            ARM_ACTION_VERIFICATION_TIMEOUT_S,
        )
        ctx.runtime_data["arm_action_verification_returned"] = True
        ctx.runtime_data["arm_action_interrupted"] = (
            "interrupting_action_id" in verification.details
        )
        ctx.runtime_data["arm_action_completion_verified"] = verification.completed
        return apply_arm_action_verification(
            result,
            verification.message,
            completed=verification.completed,
            observable=verification.observable,
            details=verification.details,
            action_id=self.spec.action_id,
            action_name=self.spec.sdk_name,
        )

    async def cleanup(self, ctx: SkillContext, args: ArmActionArgs) -> None:
        if ctx.runtime_data.get("arm_action_started") is not True:
            return
        if (
            ctx.runtime_data.get("arm_action_verification_returned") is True
            and ctx.runtime_data.get("arm_action_interrupted") is not True
            and ctx.runtime_data.get("arm_action_completion_verified") is True
        ):
            return
        await ctx.robot.release_arm()


class HandshakeArgs(SkillArgs):
    duration_s: float = Field(default=4.0, ge=1.0, le=10.0)


class HandshakeSkill(RobotSkill[HandshakeArgs]):
    metadata = SkillMetadata(
        name="handshake",
        description=(
            "Highest-priority response when a person extends a hand toward the "
            "robot around waist or lower-chest height; shake it, then release."
        ),
        tags=("gesture", "social", "sdk_preset"),
        required_resources=("upper_body",),
        timeout_s=30.0,
    )
    args_model = HandshakeArgs

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: HandshakeArgs,
    ) -> tuple[bool, str]:
        return await check_arm_action_preconditions(ctx)

    async def execute(
        self,
        ctx: SkillContext,
        args: HandshakeArgs,
    ) -> SkillResult:
        await ctx.robot.execute_arm_action(27, "shake hand")
        ctx.runtime_data["handshake_started"] = True
        await asyncio.sleep(args.duration_s)
        await ctx.robot.release_arm()
        ctx.runtime_data["handshake_released"] = True
        return SkillResult.ok(
            "handshake command sequence accepted",
            action_id=27,
            action_name="shake hand",
            duration_s=args.duration_s,
            command_accepted=True,
        )

    async def verify(
        self,
        ctx: SkillContext,
        args: HandshakeArgs,
        result: SkillResult,
    ) -> SkillResult:
        verification = await ctx.robot.wait_for_arm_action_completion(
            27,
            "handshake",
            ARM_ACTION_VERIFICATION_TIMEOUT_S,
        )
        return apply_arm_action_verification(
            result,
            verification.message,
            completed=verification.completed,
            observable=verification.observable,
            details=verification.details,
            action_id=27,
            action_name="handshake",
        )

    async def cleanup(self, ctx: SkillContext, args: HandshakeArgs) -> None:
        if (
            ctx.runtime_data.get("handshake_started") is True
            and ctx.runtime_data.get("handshake_released") is not True
        ):
            await ctx.robot.release_arm()


class ShakeHandSkill(HandshakeSkill):
    """Compatibility alias matching the SDK's ``ShakeHand`` name."""

    metadata = SkillMetadata(
        name="shake_hand",
        description="Run the SDK handshake sequence and release the arm.",
        tags=("gesture", "social", "sdk_loco"),
        required_resources=("upper_body",),
        timeout_s=30.0,
    )


class ReleaseArmSkill(RobotSkill[ArmActionArgs]):
    metadata = SkillMetadata(
        name="release_arm",
        description="Release the current G1 arm pose or handshake.",
        tags=("gesture", "safety", "sdk_preset"),
        required_resources=("upper_body",),
        timeout_s=12.0,
    )
    args_model = ArmActionArgs

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: ArmActionArgs,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""

    async def execute(
        self,
        ctx: SkillContext,
        args: ArmActionArgs,
    ) -> SkillResult:
        await ctx.robot.release_arm()
        return SkillResult.ok(
            "arm release command accepted",
            action_id=99,
            action_name="release arm",
        )


def build_preset_arm_action_skills() -> tuple[PresetArmActionSkill, ...]:
    return tuple(
        PresetArmActionSkill(spec)
        for spec in G1_ARM_ACTION_SPECS
        if spec.skill_name not in {"wave", "handshake", "release_arm"}
    )


__all__ = [
    "ARM_ACTION_VERIFICATION_TIMEOUT_S",
    "ArmActionArgs",
    "HandshakeArgs",
    "HandshakeSkill",
    "PresetArmActionSkill",
    "ReleaseArmSkill",
    "ShakeHandSkill",
    "apply_arm_action_verification",
    "build_preset_arm_action_skills",
    "check_arm_action_preconditions",
]

"""Operator-only G1 LocoClient controls excluded from autonomous policies."""

from pydantic import Field

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill


class EmptyControlArgs(SkillArgs):
    pass


class ToggleControlArgs(SkillArgs):
    enabled: bool


class SpeedModeArgs(SkillArgs):
    # The installed SDK declares an int without documenting the controller's
    # model-specific enum. Keep it bounded and operator-only.
    mode: int = Field(ge=0, le=255)


class _OperatorControlSkill[ArgsT: SkillArgs](RobotSkill[ArgsT]):
    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: ArgsT,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""


class WaveWithTurnSkill(_OperatorControlSkill[EmptyControlArgs]):
    metadata = SkillMetadata(
        name="wave_with_turn",
        description="Use the legacy G1 wave action while turning the body.",
        tags=("gesture", "sdk_loco", "operator_only"),
        required_resources=("mobile_base", "upper_body"),
        timeout_s=12.0,
    )
    args_model = EmptyControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: EmptyControlArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action("wave_with_turn")
        return SkillResult.ok("wave_with_turn command accepted")


class ContinuousGaitSkill(_OperatorControlSkill[ToggleControlArgs]):
    metadata = SkillMetadata(
        name="continuous_gait",
        description="Enable or disable the SDK continuous gait balance mode.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = ToggleControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: ToggleControlArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "continuous_gait",
            {"enabled": args.enabled},
        )
        return SkillResult.ok(
            "continuous_gait command accepted",
            enabled=args.enabled,
        )


class SwitchMoveModeSkill(_OperatorControlSkill[ToggleControlArgs]):
    metadata = SkillMetadata(
        name="switch_move_mode",
        description="Switch the SDK Move call between timed and continuous mode.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = ToggleControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: ToggleControlArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "switch_move_mode",
            {"enabled": args.enabled},
        )
        return SkillResult.ok(
            "switch_move_mode command accepted",
            enabled=args.enabled,
        )


class SetSpeedModeSkill(_OperatorControlSkill[SpeedModeArgs]):
    metadata = SkillMetadata(
        name="set_speed_mode",
        description="Set the model-specific integer G1 speed mode.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = SpeedModeArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: SpeedModeArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "set_speed_mode",
            {"mode": args.mode},
        )
        return SkillResult.ok("set_speed_mode command accepted", mode=args.mode)


def build_operator_control_skills() -> tuple[RobotSkill[SkillArgs], ...]:
    return (
        WaveWithTurnSkill(),
        ContinuousGaitSkill(),
        SwitchMoveModeSkill(),
        SetSpeedModeSkill(),
    )


__all__ = [
    "ContinuousGaitSkill",
    "EmptyControlArgs",
    "SetSpeedModeSkill",
    "SpeedModeArgs",
    "SwitchMoveModeSkill",
    "ToggleControlArgs",
    "WaveWithTurnSkill",
    "build_operator_control_skills",
]

"""Operator-only G1 LocoClient controls excluded from autonomous policies."""

from typing import Literal

from pydantic import Field, FiniteFloat

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


class FsmIdArgs(SkillArgs):
    fsm_id: int = Field(ge=0, le=999_999)


class BalanceModeArgs(SkillArgs):
    balance_mode: int = Field(ge=0, le=255)


class SwingHeightArgs(SkillArgs):
    swing_height: FiniteFloat


class StandHeightArgs(SkillArgs):
    stand_height: FiniteFloat


class SetVelocityArgs(SkillArgs):
    vx: float = Field(ge=-1.0, le=1.0)
    vy: float = Field(ge=-1.0, le=1.0)
    omega: float = Field(ge=-2.0, le=2.0)
    duration: float = Field(default=1.0, ge=0.1, le=10.0)


class SdkMoveArgs(SkillArgs):
    """Arguments for the SDK's overloaded ``LocoClient.move`` call."""

    vx: float = Field(ge=-1.0, le=1.0)
    vy: float = Field(ge=-1.0, le=1.0)
    vyaw: float = Field(ge=-2.0, le=2.0)
    continuous_move: bool = False


class TaskIdArgs(SkillArgs):
    task_id: int = Field(ge=0, le=255)


class InternalControlArgs(SkillArgs):
    mode: Literal["last", "passive", "walkrun"]


class FsmApiArgs(SkillArgs):
    parameter: str = Field(min_length=1, max_length=4096)


class CustomArmActionArgs(SkillArgs):
    action_name: str = Field(min_length=1, max_length=256)


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


class SetFsmIdSkill(_OperatorControlSkill[FsmIdArgs]):
    metadata = SkillMetadata(
        name="set_fsm_id",
        description="Set an explicit G1 locomotion FSM ID.",
        tags=("configuration", "sdk_loco", "operator_only", "dangerous"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = FsmIdArgs

    async def execute(self, ctx: SkillContext, args: FsmIdArgs) -> SkillResult:
        await ctx.robot.execute_loco_action("set_fsm_id", {"fsm_id": args.fsm_id})
        return SkillResult.ok("set_fsm_id command accepted", fsm_id=args.fsm_id)


class SetBalanceModeSkill(_OperatorControlSkill[BalanceModeArgs]):
    metadata = SkillMetadata(
        name="set_balance_mode",
        description="Set the integer G1 balance mode.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = BalanceModeArgs

    async def execute(self, ctx: SkillContext, args: BalanceModeArgs) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "set_balance_mode",
            {"balance_mode": args.balance_mode},
        )
        return SkillResult.ok(
            "set_balance_mode command accepted",
            balance_mode=args.balance_mode,
        )


class SetSwingHeightSkill(_OperatorControlSkill[SwingHeightArgs]):
    metadata = SkillMetadata(
        name="set_swing_height",
        description="Set the G1 swing height in SDK units.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = SwingHeightArgs

    async def execute(self, ctx: SkillContext, args: SwingHeightArgs) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "set_swing_height",
            {"swing_height": args.swing_height},
        )
        return SkillResult.ok(
            "set_swing_height command accepted",
            swing_height=args.swing_height,
        )


class SetStandHeightSkill(_OperatorControlSkill[StandHeightArgs]):
    metadata = SkillMetadata(
        name="set_stand_height",
        description="Set the G1 stand height in SDK units.",
        tags=("configuration", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
    )
    args_model = StandHeightArgs

    async def execute(self, ctx: SkillContext, args: StandHeightArgs) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "set_stand_height",
            {"stand_height": args.stand_height},
        )
        return SkillResult.ok(
            "set_stand_height command accepted",
            stand_height=args.stand_height,
        )


class SetVelocitySkill(_OperatorControlSkill[SetVelocityArgs]):
    metadata = SkillMetadata(
        name="set_velocity",
        description="Send one bounded SDK velocity command with a finite duration.",
        tags=("motion", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=15.0,
    )
    args_model = SetVelocityArgs

    async def execute(self, ctx: SkillContext, args: SetVelocityArgs) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "set_velocity",
            {
                "vx": args.vx,
                "vy": args.vy,
                "omega": args.omega,
                "duration": args.duration,
            },
        )
        return SkillResult.ok(
            "set_velocity command accepted",
            vx=args.vx,
            vy=args.vy,
            omega=args.omega,
            duration=args.duration,
        )


class SdkMoveSkill(_OperatorControlSkill[SdkMoveArgs]):
    metadata = SkillMetadata(
        name="move_sdk",
        description="Call the SDK's overloaded LocoClient.move API directly.",
        tags=("motion", "sdk_loco", "operator_only"),
        required_resources=("mobile_base",),
        timeout_s=15.0,
    )
    args_model = SdkMoveArgs

    async def execute(self, ctx: SkillContext, args: SdkMoveArgs) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "move_sdk",
            {
                "vx": args.vx,
                "vy": args.vy,
                "vyaw": args.vyaw,
                "continuous_move": args.continuous_move,
            },
        )
        return SkillResult.ok(
            "move_sdk command accepted",
            vx=args.vx,
            vy=args.vy,
            vyaw=args.vyaw,
            continuous_move=args.continuous_move,
        )


class SetTaskIdSkill(_OperatorControlSkill[TaskIdArgs]):
    metadata = SkillMetadata(
        name="set_task_id",
        description="Set an explicit G1 arm-task ID through LocoClient.",
        tags=("configuration", "sdk_loco", "operator_only", "dangerous"),
        required_resources=("upper_body",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = TaskIdArgs

    async def execute(self, ctx: SkillContext, args: TaskIdArgs) -> SkillResult:
        await ctx.robot.execute_loco_action("set_task_id", {"task_id": args.task_id})
        return SkillResult.ok("set_task_id command accepted", task_id=args.task_id)


class SwitchToUserControlSkill(_OperatorControlSkill[EmptyControlArgs]):
    metadata = SkillMetadata(
        name="switch_to_user_ctrl",
        description="Switch G1 control to the user controller.",
        tags=("configuration", "sdk_loco", "operator_only", "dangerous"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = EmptyControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: EmptyControlArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action("switch_to_user_ctrl")
        return SkillResult.ok("switch_to_user_ctrl command accepted")


class SwitchToInternalControlSkill(_OperatorControlSkill[InternalControlArgs]):
    metadata = SkillMetadata(
        name="switch_to_internal_ctrl",
        description="Switch G1 control to an SDK internal FSM mode.",
        tags=("configuration", "sdk_loco", "operator_only", "dangerous"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = InternalControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: InternalControlArgs,
    ) -> SkillResult:
        await ctx.robot.execute_loco_action(
            "switch_to_internal_ctrl",
            {"mode": args.mode},
        )
        return SkillResult.ok(
            "switch_to_internal_ctrl command accepted",
            mode=args.mode,
        )


class FsmApiSkill(_OperatorControlSkill[FsmApiArgs]):
    metadata = SkillMetadata(
        name="fsm_api",
        description="Send a raw JSON parameter to the G1 locomotion FSM API.",
        tags=("advanced", "sdk_loco", "operator_only", "dangerous"),
        required_resources=("mobile_base",),
        timeout_s=15.0,
        interruptible=False,
    )
    args_model = FsmApiArgs

    async def execute(self, ctx: SkillContext, args: FsmApiArgs) -> SkillResult:
        await ctx.robot.execute_loco_action("fsm_api", {"parameter": args.parameter})
        return SkillResult.ok("fsm_api command accepted")


class ExecuteCustomArmActionSkill(_OperatorControlSkill[CustomArmActionArgs]):
    metadata = SkillMetadata(
        name="execute_custom_arm_action",
        description="Execute a named G1 teach/custom arm action.",
        tags=("gesture", "sdk_arm", "operator_only", "dangerous"),
        required_resources=("upper_body",),
        timeout_s=30.0,
        interruptible=False,
    )
    args_model = CustomArmActionArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: CustomArmActionArgs,
    ) -> SkillResult:
        await ctx.robot.execute_custom_arm_action(args.action_name)
        return SkillResult.ok(
            "custom arm action command accepted",
            action_name=args.action_name,
        )


class StopCustomArmActionSkill(_OperatorControlSkill[EmptyControlArgs]):
    metadata = SkillMetadata(
        name="stop_custom_arm_action",
        description="Stop the currently running named G1 teach/custom arm action.",
        tags=("gesture", "safety", "sdk_arm", "operator_only"),
        required_resources=("upper_body",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = EmptyControlArgs

    async def execute(
        self,
        ctx: SkillContext,
        args: EmptyControlArgs,
    ) -> SkillResult:
        await ctx.robot.stop_custom_arm_action()
        return SkillResult.ok("stop_custom_arm_action command accepted")


def build_operator_control_skills() -> tuple[RobotSkill[SkillArgs], ...]:
    return (
        WaveWithTurnSkill(),
        ContinuousGaitSkill(),
        SwitchMoveModeSkill(),
        SetSpeedModeSkill(),
        SetFsmIdSkill(),
        SetBalanceModeSkill(),
        SetSwingHeightSkill(),
        SetStandHeightSkill(),
        SetVelocitySkill(),
        SdkMoveSkill(),
        SetTaskIdSkill(),
        SwitchToUserControlSkill(),
        SwitchToInternalControlSkill(),
        FsmApiSkill(),
        ExecuteCustomArmActionSkill(),
        StopCustomArmActionSkill(),
    )


__all__ = [
    "BalanceModeArgs",
    "ContinuousGaitSkill",
    "CustomArmActionArgs",
    "EmptyControlArgs",
    "ExecuteCustomArmActionSkill",
    "FsmApiArgs",
    "FsmApiSkill",
    "FsmIdArgs",
    "InternalControlArgs",
    "SdkMoveArgs",
    "SdkMoveSkill",
    "SetBalanceModeSkill",
    "SetFsmIdSkill",
    "SetSpeedModeSkill",
    "SetStandHeightSkill",
    "SetSwingHeightSkill",
    "SetTaskIdSkill",
    "SetVelocityArgs",
    "SetVelocitySkill",
    "SpeedModeArgs",
    "StandHeightArgs",
    "StopCustomArmActionSkill",
    "SwingHeightArgs",
    "SwitchMoveModeSkill",
    "SwitchToInternalControlSkill",
    "SwitchToUserControlSkill",
    "TaskIdArgs",
    "ToggleControlArgs",
    "WaveWithTurnSkill",
    "build_operator_control_skills",
]

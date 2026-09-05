"""Bounded open-loop G1 translation, rotation, and stop skills."""

from __future__ import annotations

import asyncio
import math

from pydantic import Field

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.skill import RobotSkill


class LinearMoveArgs(SkillArgs):
    distance_m: float = Field(default=0.2, ge=0.05, le=0.3)


class TurnArgs(SkillArgs):
    angle_deg: float = Field(default=15.0, ge=5.0, le=45.0)


class StopArgs(SkillArgs):
    pass


class MoveArgs(SkillArgs):
    forward_m_s: float = Field(default=0.1, ge=-0.3, le=0.3)
    lateral_m_s: float = Field(default=0.0, ge=-0.3, le=0.3)
    yaw_rad_s: float = Field(default=0.0, ge=-0.6, le=0.6)
    duration_s: float = Field(default=0.5, ge=0.1, le=2.0)


class _BoundedMotionSkill[ArgsT: SkillArgs](RobotSkill[ArgsT]):
    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: ArgsT,
    ) -> tuple[bool, str]:
        state = await ctx.robot.get_state()
        if state.hardware and not state.connected:
            return False, "robot is not connected"
        return True, ""

    async def cleanup(self, ctx: SkillContext, args: ArgsT) -> None:
        if (
            ctx.runtime_data.get("motion_attempted") is True
            and ctx.runtime_data.get("motion_stopped") is not True
        ):
            await ctx.robot.stop()


class _LinearMoveSkill(_BoundedMotionSkill[LinearMoveArgs]):
    args_model = LinearMoveArgs
    forward_sign = 0.0
    lateral_sign = 0.0
    result_label = "movement"

    async def execute(
        self,
        ctx: SkillContext,
        args: LinearMoveArgs,
    ) -> SkillResult:
        speed_m_s = min(max(args.distance_m, 0.1), 0.3)
        duration_s = args.distance_m / speed_m_s
        forward_m_s = self.forward_sign * speed_m_s
        lateral_m_s = self.lateral_sign * speed_m_s
        ctx.runtime_data["motion_attempted"] = True
        await ctx.robot.move_velocity(forward_m_s, lateral_m_s, 0.0)
        await asyncio.sleep(duration_s)
        await ctx.robot.stop()
        ctx.runtime_data["motion_stopped"] = True
        return SkillResult.ok(
            f"{self.result_label} completed",
            distance_m=args.distance_m,
            speed_m_s=speed_m_s,
        )


class MoveForwardSkill(_LinearMoveSkill):
    metadata = SkillMetadata(
        name="move_forward",
        description="Move forward by a short bounded distance, then stop.",
        tags=("motion",),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    forward_sign = 1.0
    result_label = "forward movement"


class MoveLeftSkill(_LinearMoveSkill):
    metadata = SkillMetadata(
        name="move_left",
        description="Step left by a short bounded distance, then stop.",
        tags=("motion",),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    lateral_sign = 1.0
    result_label = "left movement"


class MoveRightSkill(_LinearMoveSkill):
    metadata = SkillMetadata(
        name="move_right",
        description="Step right by a short bounded distance, then stop.",
        tags=("motion",),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    lateral_sign = -1.0
    result_label = "right movement"


class _TurnSkill(_BoundedMotionSkill[TurnArgs]):
    args_model = TurnArgs
    yaw_sign = 1.0
    result_label = "turn"

    async def execute(
        self,
        ctx: SkillContext,
        args: TurnArgs,
    ) -> SkillResult:
        angle_rad = math.radians(args.angle_deg)
        yaw_rad_s = min(max(angle_rad, 0.25), 0.6)
        duration_s = angle_rad / yaw_rad_s
        ctx.runtime_data["motion_attempted"] = True
        await ctx.robot.move_velocity(0.0, 0.0, self.yaw_sign * yaw_rad_s)
        await asyncio.sleep(duration_s)
        await ctx.robot.stop()
        ctx.runtime_data["motion_stopped"] = True
        return SkillResult.ok(
            f"{self.result_label} completed",
            angle_deg=args.angle_deg,
            yaw_rad_s=yaw_rad_s,
        )


class TurnLeftSkill(_TurnSkill):
    metadata = SkillMetadata(
        name="turn_left",
        description="Turn left by a small bounded angle, then stop.",
        tags=("motion",),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    yaw_sign = 1.0
    result_label = "left turn"


class TurnRightSkill(_TurnSkill):
    metadata = SkillMetadata(
        name="turn_right",
        description="Turn right by a small bounded angle, then stop.",
        tags=("motion",),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    yaw_sign = -1.0
    result_label = "right turn"


class MoveSkill(_BoundedMotionSkill[MoveArgs]):
    """Direct bounded wrapper for the SDK's generic ``LocoClient.move`` API."""

    metadata = SkillMetadata(
        name="move",
        description="Move with bounded forward, lateral, and yaw velocities, then stop.",
        tags=("motion", "sdk_loco"),
        required_resources=("mobile_base",),
        timeout_s=6.0,
    )
    args_model = MoveArgs

    async def execute(self, ctx: SkillContext, args: MoveArgs) -> SkillResult:
        ctx.runtime_data["motion_attempted"] = True
        await ctx.robot.move_velocity(
            args.forward_m_s,
            args.lateral_m_s,
            args.yaw_rad_s,
        )
        await asyncio.sleep(args.duration_s)
        await ctx.robot.stop()
        ctx.runtime_data["motion_stopped"] = True
        return SkillResult.ok(
            "generic bounded movement completed",
            forward_m_s=args.forward_m_s,
            lateral_m_s=args.lateral_m_s,
            yaw_rad_s=args.yaw_rad_s,
            duration_s=args.duration_s,
        )


class StopSkill(RobotSkill[StopArgs]):
    metadata = SkillMetadata(
        name="stop",
        description="Stop locomotion and release the current arm pose.",
        tags=("motion", "safety"),
        required_resources=("mobile_base", "upper_body"),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = StopArgs

    async def execute(self, ctx: SkillContext, args: StopArgs) -> SkillResult:
        await ctx.robot.stop()
        await ctx.robot.release_arm()
        return SkillResult.ok("robot software stop commands accepted")


class StopMoveSkill(RobotSkill[StopArgs]):
    """Compatibility skill matching the SDK's ``StopMove`` call."""

    metadata = SkillMetadata(
        name="stop_move",
        description="Stop the G1 locomotion controller.",
        tags=("motion", "safety", "sdk_loco"),
        required_resources=("mobile_base",),
        timeout_s=12.0,
        interruptible=False,
    )
    args_model = StopArgs

    async def execute(self, ctx: SkillContext, args: StopArgs) -> SkillResult:
        await ctx.robot.stop()
        return SkillResult.ok("stop_move command accepted")


__all__ = [
    "LinearMoveArgs",
    "MoveArgs",
    "MoveForwardSkill",
    "MoveLeftSkill",
    "MoveRightSkill",
    "MoveSkill",
    "StopArgs",
    "StopMoveSkill",
    "StopSkill",
    "TurnArgs",
    "TurnLeftSkill",
    "TurnRightSkill",
]

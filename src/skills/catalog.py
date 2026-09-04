"""Canonical G1 skill catalogs used by every application entry point."""

from typing import cast

from core.models import SkillArgs
from core.runtime import SkillRuntime
from core.skill import RobotSkill

from .motions import (
    HandshakeSkill,
    MoveBackwardSkill,
    MoveForwardSkill,
    MoveLeftSkill,
    MoveRightSkill,
    ReleaseArmSkill,
    StopSkill,
    TurnLeftSkill,
    TurnRightSkill,
    WaveSkill,
    build_operator_control_skills,
    build_preset_arm_action_skills,
)
from .posture import build_posture_skills


def build_g1_autonomy_skills() -> tuple[RobotSkill[SkillArgs], ...]:
    skills = (
        WaveSkill(),
        HandshakeSkill(),
        *build_preset_arm_action_skills(),
        ReleaseArmSkill(),
        *build_posture_skills(operator_only=False),
        MoveForwardSkill(),
        MoveBackwardSkill(),
        MoveLeftSkill(),
        MoveRightSkill(),
        TurnLeftSkill(),
        TurnRightSkill(),
        StopSkill(),
    )
    return cast(tuple[RobotSkill[SkillArgs], ...], skills)


def build_g1_operator_skills() -> tuple[RobotSkill[SkillArgs], ...]:
    skills = (
        *build_posture_skills(operator_only=True),
        *build_operator_control_skills(),
    )
    return cast(tuple[RobotSkill[SkillArgs], ...], skills)


def register_g1_skills(
    runtime: SkillRuntime,
    *,
    include_operator_only: bool = False,
) -> None:
    skills = list(build_g1_autonomy_skills())
    if include_operator_only:
        skills.extend(build_g1_operator_skills())
    for skill in skills:
        runtime.register(skill)


__all__ = [
    "build_g1_autonomy_skills",
    "build_g1_operator_skills",
    "register_g1_skills",
]

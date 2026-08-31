"""In-memory registration and lookup for robot skills."""

from typing import cast

from pydantic import BaseModel

from .skill import RobotSkill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RobotSkill[BaseModel]] = {}

    def register[ArgsT: BaseModel](self, skill: RobotSkill[ArgsT]) -> None:
        name = skill.metadata.name
        if name in self._skills:
            raise ValueError(f"duplicate skill: {name}")
        self._skills[name] = cast(RobotSkill[BaseModel], cast(object, skill))

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def get(self, name: str) -> RobotSkill[BaseModel]:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"unknown skill: {name}") from exc

    def exists(self, name: str) -> bool:
        return name in self._skills

    def list(self) -> tuple[RobotSkill[BaseModel], ...]:
        return tuple(self._skills.values())

"""Public facade for registering and invoking robot skills."""

from pydantic import BaseModel

from robot.base import RobotAdapter

from .executor import SkillExecutor
from .models import SkillInvocation, SkillResult
from .registry import SkillRegistry
from .skill import RobotSkill


class SkillRuntime:
    def __init__(self, robot: RobotAdapter) -> None:
        self.robot = robot
        self.registry = SkillRegistry()
        self.executor = SkillExecutor(self.registry, robot)

    def register[ArgsT: BaseModel](self, skill: RobotSkill[ArgsT]) -> None:
        self.registry.register(skill)

    async def execute(
        self,
        skill_name: str,
        *,
        request_id: str | None = None,
        source: str | None = None,
        **arguments: object,
    ) -> SkillResult:
        return await self.executor.execute(
            SkillInvocation(
                skill_name=skill_name,
                arguments=arguments,
                request_id=request_id,
                source=source,
            )
        )

"""Public facade for registering and invoking robot skills."""

from robot.base import RobotAdapter

from .executor import SkillExecutor
from .models import SkillArgs, SkillInvocation, SkillResult
from .registry import SkillRegistry
from .resources import ResourceManager
from .skill import RobotSkill


class SkillRuntime:
    def __init__(self, robot: RobotAdapter) -> None:
        self.robot = robot
        self.registry = SkillRegistry()
        self.resources = ResourceManager()
        self.executor = SkillExecutor(self.registry, robot, self.resources)

    def register[ArgsT: SkillArgs](self, skill: RobotSkill[ArgsT]) -> None:
        self.registry.register(skill)

    async def execute(
        self,
        skill_name: str,
        /,
        **arguments: object,
    ) -> SkillResult:
        return await self.executor.execute(
            SkillInvocation(
                skill_name=skill_name,
                arguments=arguments,
            )
        )

"""Base class and lifecycle contract for robot skills."""

from abc import ABC, abstractmethod

from .context import SkillContext
from .models import SkillArgs, SkillMetadata, SkillResult


class RobotSkill[ArgsT: SkillArgs](ABC):
    metadata: SkillMetadata
    args_model: type[ArgsT]

    async def check_preconditions(
        self,
        ctx: SkillContext,
        args: ArgsT,
    ) -> tuple[bool, str]:
        return True, ""

    @abstractmethod
    async def execute(self, ctx: SkillContext, args: ArgsT) -> SkillResult:
        """Execute the skill after its arguments and preconditions are valid."""

    async def cleanup(self, ctx: SkillContext, args: ArgsT) -> None:
        """Release skill-local state after an attempted execution."""

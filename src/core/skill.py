"""Base class and lifecycle contract for robot skills."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from .context import SkillContext
from .models import SkillMetadata, SkillResult


class RobotSkill[ArgsT: BaseModel](ABC):
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

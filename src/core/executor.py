"""Lifecycle executor for a single skill invocation."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from pydantic import ValidationError

from robot.base import RobotAdapter, RobotCommandError

from .context import SkillContext
from .models import SkillArgs, SkillInvocation, SkillResult
from .registry import SkillRegistry
from .resources import ResourceManager
from .skill import RobotSkill
from .types import FailureCode, SkillStatus

logger = logging.getLogger(__name__)


class SkillExecutor:
    def __init__(
        self,
        registry: SkillRegistry,
        robot: RobotAdapter,
        resources: ResourceManager | None = None,
    ) -> None:
        self.registry = registry
        self.robot = robot
        self.resources = resources or ResourceManager()

    async def execute(self, invocation: SkillInvocation) -> SkillResult:
        started = time.monotonic()

        try:
            skill = self.registry.get(invocation.skill_name)
        except KeyError:
            return self._finish(
                SkillResult.fail(
                    SkillStatus.FAILED,
                    f"unknown skill: {invocation.skill_name}",
                    failure_code=FailureCode.INVALID_ARGUMENTS,
                ),
                started,
            )

        try:
            args = skill.args_model.model_validate(invocation.arguments)
        except ValidationError as exc:
            return self._finish(
                SkillResult.fail(
                    SkillStatus.FAILED,
                    f"invalid arguments: {exc}",
                    failure_code=FailureCode.INVALID_ARGUMENTS,
                ),
                started,
            )

        ctx = SkillContext(robot=self.robot, execution_id=str(uuid.uuid4()))
        result: SkillResult

        async with self.resources.acquire(skill.metadata.required_resources):
            result = await self._execute_with_cleanup(skill, ctx, args)

        return self._finish(result, started)

    async def _execute_with_cleanup(
        self,
        skill: RobotSkill[SkillArgs],
        ctx: SkillContext,
        args: SkillArgs,
    ) -> SkillResult:
        try:
            ready, reason = await skill.check_preconditions(ctx, args)
            if not ready:
                return SkillResult.fail(
                    SkillStatus.PRECONDITION_FAILED,
                    reason or "skill precondition not met",
                    failure_code=FailureCode.PRECONDITION_NOT_MET,
                    recoverable=True,
                )
            return await asyncio.wait_for(
                skill.execute(ctx, args),
                timeout=skill.metadata.timeout_s,
            )
        except TimeoutError:
            return SkillResult.fail(
                SkillStatus.TIMEOUT,
                "skill execution timeout",
                failure_code=FailureCode.TIMEOUT,
            )
        except asyncio.CancelledError:
            raise
        except RobotCommandError as exc:
            return SkillResult.fail(
                SkillStatus.FAILED,
                str(exc),
                failure_code=FailureCode.ROBOT_ERROR,
            )
        except Exception as exc:  # noqa: BLE001 - isolate third-party skill failures
            return SkillResult.fail(
                SkillStatus.FAILED,
                f"execution exception: {exc}",
                failure_code=FailureCode.EXECUTION_ERROR,
            )
        finally:
            try:
                await skill.cleanup(ctx, args)
            except Exception:
                logger.exception("skill cleanup failed: %s", skill.metadata.name)

    @staticmethod
    def _finish(result: SkillResult, started: float) -> SkillResult:
        result.duration_s = time.monotonic() - started
        return result

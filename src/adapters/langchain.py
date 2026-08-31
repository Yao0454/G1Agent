"""Expose registered robot skills as LangChain structured tools."""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, StructuredTool

from core.models import SkillArgs
from core.runtime import SkillRuntime
from core.skill import RobotSkill


def build_langchain_tools(runtime: SkillRuntime) -> tuple[BaseTool, ...]:
    return tuple(_build_skill_tool(runtime, skill) for skill in runtime.registry.list())


def _build_skill_tool(
    runtime: SkillRuntime,
    skill: RobotSkill[SkillArgs],
) -> BaseTool:
    skill_name = skill.metadata.name

    async def invoke_skill(**arguments: object) -> str:
        result = await runtime.execute(skill_name, **arguments)
        return json.dumps(result.to_dict(), ensure_ascii=False, default=str)

    return StructuredTool.from_function(
        coroutine=invoke_skill,
        name=skill_name,
        description=skill.metadata.description,
        args_schema=skill.args_model,
        infer_schema=False,
    )

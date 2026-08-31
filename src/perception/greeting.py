"""Environment-triggered behavior: greet a newly visible person once."""

from __future__ import annotations

import asyncio

from core.models import SkillResult
from core.runtime import SkillRuntime

from .models import PerceptionResult
from .world_state import WorldState


class PersonGreetingLoop:
    def __init__(
        self,
        runtime: SkillRuntime,
        world_state: WorldState | None = None,
    ) -> None:
        self.runtime = runtime
        self.world_state = world_state or WorldState()
        self._lock = asyncio.Lock()

    async def process(self, result: PerceptionResult) -> SkillResult | None:
        async with self._lock:
            self.world_state.observe(result)
            if not self.world_state.should_greet(result.observed_at_s):
                return None

            self.world_state.mark_greeting_attempt(result.observed_at_s)
            skill_result = await self.runtime.execute("wave", arm="right")
            if skill_result.success:
                self.world_state.mark_greeted()
            return skill_result

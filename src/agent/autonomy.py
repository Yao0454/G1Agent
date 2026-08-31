"""Execute event decisions through SkillRuntime and optional speech output."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from adapters.unitree_audio import SpeechOutput
from core.models import SkillResult
from core.runtime import SkillRuntime
from perception import EventDetector, PerceptionResult, WorldEvent, WorldState

from .decision import AgentDecision, DecisionAgent


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    event: WorldEvent
    decision: AgentDecision
    skill_result: SkillResult | None = None
    speech_spoken: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "event": self.event.to_dict(),
            "decision": self.decision.to_dict(),
            "skill_result": (
                self.skill_result.to_dict() if self.skill_result is not None else None
            ),
            "speech_spoken": self.speech_spoken,
        }


class AutonomousDecisionLoop:
    def __init__(
        self,
        runtime: SkillRuntime,
        decision_agent: DecisionAgent,
        *,
        world_state: WorldState | None = None,
        event_detector: EventDetector | None = None,
        speech: SpeechOutput | None = None,
    ) -> None:
        self.runtime = runtime
        self.decision_agent = decision_agent
        self.world_state = world_state or WorldState()
        self.event_detector = event_detector or EventDetector()
        self.speech = speech
        self._lock = asyncio.Lock()

    async def process(
        self,
        observation: PerceptionResult,
    ) -> tuple[DecisionOutcome, ...]:
        async with self._lock:
            events = self.event_detector.update(observation, self.world_state)
            outcomes: list[DecisionOutcome] = []
            for event in events:
                decision = await self.decision_agent.decide(
                    event,
                    self.world_state.to_dict(),
                )
                outcomes.append(await self._execute(event, decision))
            return tuple(outcomes)

    async def _execute(
        self,
        event: WorldEvent,
        decision: AgentDecision,
    ) -> DecisionOutcome:
        skill_result: SkillResult | None = None
        if decision.action in {"execute_skill", "execute_and_speak"}:
            if decision.skill is None:
                raise RuntimeError("validated decision is missing a skill")
            skill_result = await self.runtime.execute(
                decision.skill,
                **decision.arguments,
            )
            if (
                skill_result.success
                and decision.skill == "wave"
                and self.world_state.person_visible
            ):
                self.world_state.mark_greeted()

        speech_spoken = False
        if decision.action in {"speak", "execute_and_speak"}:
            if decision.speech is None:
                raise RuntimeError("validated decision is missing speech")
            if self.speech is not None:
                await self.speech.speak(decision.speech)
                speech_spoken = True

        return DecisionOutcome(
            event=event,
            decision=decision,
            skill_result=skill_result,
            speech_spoken=speech_spoken,
        )

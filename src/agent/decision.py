"""Structured LangChain decision Agent for sparse world events."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Literal, Protocol, Self, cast

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from perception.events import WorldEvent

DECISION_SYSTEM_PROMPT = """You are the event decision layer for a Unitree G1.

Return exactly one structured AgentDecision. Do not call robot SDKs directly.
Available skills are wave and move_backward.

- For person_entered when person_greeted is false, wave and greet briefly.
- For person_too_close, move backward 0.2 to 0.3 meters and politely ask for space.
- For person_left or an event requiring no behavior, ignore it.

Use only arguments accepted by the selected skill. Keep speech concise and use
Chinese unless the event context explicitly requests another language. Never
invent another skill.
"""

DecisionAction = Literal[
    "execute_skill",
    "speak",
    "execute_and_speak",
    "ignore",
]
DecisionSkill = Literal["wave", "move_backward"]


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    skill: DecisionSkill | None = None
    arguments: dict[str, object] = Field(default_factory=dict)
    speech: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_action_contract(self) -> Self:
        executes = self.action in {"execute_skill", "execute_and_speak"}
        speaks = self.action in {"speak", "execute_and_speak"}
        if executes and self.skill is None:
            raise ValueError(f"{self.action} requires a skill")
        if not executes and (self.skill is not None or self.arguments):
            raise ValueError(f"{self.action} must not include a skill or arguments")
        if speaks and (self.speech is None or not self.speech.strip()):
            raise ValueError(f"{self.action} requires non-empty speech")
        if not speaks and self.speech is not None:
            raise ValueError(f"{self.action} must not include speech")
        return self

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class DecisionAgentError(RuntimeError):
    """Raised when the decision Agent does not return a valid decision."""


class DecisionAgent(Protocol):
    async def decide(
        self,
        event: WorldEvent,
        world_state: Mapping[str, object],
    ) -> AgentDecision: ...


class DecisionInvoker(Protocol):
    async def ainvoke(self, input_state: dict[str, object]) -> object: ...


class EventDecisionAgent:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        base_url: str | None = None,
        invoker: DecisionInvoker | None = None,
    ) -> None:
        if invoker is not None:
            self._invoker = invoker
            return

        model = ChatOllama(
            model=model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
            base_url=base_url or os.getenv("OLLAMA_HOST"),
            temperature=0.1,
            client_kwargs={"trust_env": False},
        )
        graph = create_agent(
            model=model,
            tools=(),
            system_prompt=DECISION_SYSTEM_PROMPT,
            response_format=ToolStrategy(AgentDecision),
        )
        self._invoker = cast(DecisionInvoker, cast(object, graph))

    async def decide(
        self,
        event: WorldEvent,
        world_state: Mapping[str, object],
    ) -> AgentDecision:
        payload = {
            "event": event.to_dict(),
            "world_state": dict(world_state),
        }
        input_state: dict[str, object] = {
            "messages": [
                HumanMessage(
                    content=json.dumps(payload, ensure_ascii=False, default=str)
                )
            ]
        }
        try:
            output = await self._invoker.ainvoke(input_state)
        except Exception as exc:
            raise DecisionAgentError(f"Decision Agent invocation failed: {exc}") from exc
        if not isinstance(output, Mapping):
            raise DecisionAgentError("Decision Agent returned an invalid state")
        try:
            return AgentDecision.model_validate(output.get("structured_response"))
        except ValidationError as exc:
            raise DecisionAgentError(
                f"Decision Agent returned an invalid decision: {exc}"
            ) from exc

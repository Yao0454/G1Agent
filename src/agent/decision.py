"""Structured LangChain decision Agent for sparse world events."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from typing import Literal, Protocol, Self, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from perception.events import WorldEvent, WorldEventType

DECISION_SYSTEM_PROMPT = """Select one Unitree G1 response for the supplied event.
Output only a JSON object. Its top-level keys are action, skill, arguments,
speech, and optionally reason. Never wrap the object in a decision key.

Allowed responses:
- person_entered: {"action":"execute_and_speak","skill":"wave",
  "arguments":{"arm":"right"},"speech":"你好！"}
- person_too_close: {"action":"execute_and_speak","skill":"move_backward",
  "arguments":{"distance_m":0.2},"speech":"请稍微保持一点距离。"}
- person_left or no behavior: {"action":"ignore","arguments":{}}

Do not invent skills or arguments. Keep Chinese speech brief.
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

    @field_validator("skill", "speech", "reason", mode="before")
    @classmethod
    def normalize_empty_optional_string(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

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


class _StructuredDecisionModel(Protocol):
    async def ainvoke(self, messages: list[BaseMessage]) -> object: ...


class _StructuredDecisionInvoker:
    """Adapt one structured model call to the testable invoker contract."""

    def __init__(self, model: _StructuredDecisionModel) -> None:
        self._model = model

    async def ainvoke(self, input_state: dict[str, object]) -> object:
        raw_messages = input_state.get("messages")
        if not isinstance(raw_messages, list) or not all(
            isinstance(message, BaseMessage) for message in raw_messages
        ):
            raise TypeError("Decision Agent input must contain messages")
        result = await self._model.ainvoke(
            [SystemMessage(content=DECISION_SYSTEM_PROMPT), *raw_messages]
        )
        return {"structured_response": result}


class EventDecisionAgent:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        base_url: str | None = None,
        invoker: DecisionInvoker | None = None,
        timeout_s: float = 8.0,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("decision timeout must be greater than zero")
        self.timeout_s = timeout_s
        if invoker is not None:
            self._invoker = invoker
            return

        model = ChatOllama(
            model=model_name or os.getenv("OLLAMA_MODEL", "qwen3:1.7b"),
            base_url=base_url or os.getenv("OLLAMA_HOST"),
            temperature=0.1,
            reasoning=False,
            num_ctx=1024,
            num_predict=64,
            keep_alive="30m",
            client_kwargs={"trust_env": False, "timeout": timeout_s},
        )
        structured_model = model.with_structured_output(
            AgentDecision,
            method="json_mode",
        )
        self._invoker = _StructuredDecisionInvoker(
            cast(_StructuredDecisionModel, cast(object, structured_model))
        )

    async def decide(
        self,
        event: WorldEvent,
        world_state: Mapping[str, object],
    ) -> AgentDecision:
        if event.type == WorldEventType.PERSON_LEFT:
            return AgentDecision(action="ignore")

        payload = {
            "instruction": (
                f"Select only the response mapped to {event.type.value!r}; "
                "do not select an example for another event type."
            ),
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
            async with asyncio.timeout(self.timeout_s):
                output = await self._invoker.ainvoke(input_state)
        except TimeoutError as exc:
            raise DecisionAgentError(
                f"Decision Agent timed out after {self.timeout_s:g} seconds"
            ) from exc
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

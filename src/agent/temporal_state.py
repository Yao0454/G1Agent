"""Bounded cross-window state for continuous visual reasoning."""

from __future__ import annotations

import time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .decision import AgentDecision


class TemporalVisionStateUpdate(BaseModel):
    """Model-proposed changes to descriptive visual memory.

    Timestamps and completed robot actions are deliberately absent: those are
    local runtime facts and must not be supplied by the remote model.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_summary: str | None = Field(default=None, max_length=600)
    human_intent: str | None = Field(default=None, max_length=240)
    interaction_state: str | None = Field(default=None, max_length=320)
    last_observation: str | None = Field(default=None, max_length=320)

    @field_validator(
        "scene_summary",
        "human_intent",
        "interaction_state",
        "last_observation",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class TemporalVisionState(BaseModel):
    """Small, immutable cognitive state carried between video windows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_summary: str = Field(default="", max_length=600)
    human_intent: str | None = Field(default=None, max_length=240)
    interaction_state: str | None = Field(default=None, max_length=320)
    last_observation: str | None = Field(default=None, max_length=320)
    last_action: str | None = Field(default=None, max_length=160)
    updated_at_s: float = Field(default=0.0, ge=0.0)

    def apply(
        self,
        update: TemporalVisionStateUpdate,
        *,
        updated_at_s: float | None = None,
    ) -> Self:
        changes = update.model_dump(exclude_unset=True)
        if not changes:
            return self
        if "scene_summary" in changes and changes["scene_summary"] is None:
            changes["scene_summary"] = ""
        changes["updated_at_s"] = (
            time.monotonic() if updated_at_s is None else updated_at_s
        )
        return self.model_copy(update=changes)

    def record_action(
        self,
        action: str,
        *,
        updated_at_s: float | None = None,
    ) -> Self:
        normalized = action.strip()
        if not normalized:
            return self
        return self.model_copy(
            update={
                "last_action": normalized[:160],
                "updated_at_s": (
                    time.monotonic() if updated_at_s is None else updated_at_s
                ),
            }
        )

    def to_context(self, *, now_s: float | None = None) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        if self.updated_at_s > 0:
            current = time.monotonic() if now_s is None else now_s
            payload["age_s"] = round(max(0.0, current - self.updated_at_s), 3)
        else:
            payload["age_s"] = None
        return payload


class VisionDecisionResponse(BaseModel):
    """Remote response envelope for a decision plus temporal state changes."""

    model_config = ConfigDict(extra="forbid")

    decision: AgentDecision
    state_update: TemporalVisionStateUpdate

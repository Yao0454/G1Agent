"""World events derived from changes in the minimal perception state."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .models import PerceptionResult
from .world_state import WorldState


class WorldEventType(str, Enum):
    PERSON_ENTERED = "person_entered"
    PERSON_LEFT = "person_left"
    PERSON_TOO_CLOSE = "person_too_close"


class WorldEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: WorldEventType
    timestamp_s: float = Field(ge=0)
    entity_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class EventDetector:
    """Convert person-state transitions into sparse events for the Agent."""

    def __init__(
        self,
        *,
        too_close_distance_m: float = 0.8,
        too_close_release_m: float = 1.0,
    ) -> None:
        if too_close_distance_m <= 0:
            raise ValueError("too_close_distance_m must be greater than zero")
        if too_close_release_m <= too_close_distance_m:
            raise ValueError(
                "too_close_release_m must be greater than too_close_distance_m"
            )
        self.too_close_distance_m = too_close_distance_m
        self.too_close_release_m = too_close_release_m

    def update(
        self,
        observation: PerceptionResult,
        world_state: WorldState,
    ) -> tuple[WorldEvent, ...]:
        was_visible = world_state.person_visible
        was_too_close = world_state.person_too_close
        world_state.observe(observation)

        if was_visible and not world_state.person_visible:
            return (
                WorldEvent(
                    type=WorldEventType.PERSON_LEFT,
                    timestamp_s=observation.observed_at_s,
                    entity_id="nearest_person",
                ),
            )
        if not observation.person_detected:
            return ()

        distance_m = observation.nearest_person_distance_m
        is_too_close = (
            distance_m is not None and distance_m <= self.too_close_distance_m
        )
        if is_too_close:
            world_state.person_too_close = True
            if not was_too_close:
                return (
                    self._person_event(
                        WorldEventType.PERSON_TOO_CLOSE,
                        observation,
                    ),
                )
            return ()

        if (
            was_too_close
            and distance_m is not None
            and distance_m >= self.too_close_release_m
        ):
            world_state.person_too_close = False

        if not was_visible:
            return (
                self._person_event(
                    WorldEventType.PERSON_ENTERED,
                    observation,
                ),
            )
        return ()

    @staticmethod
    def _person_event(
        event_type: WorldEventType,
        observation: PerceptionResult,
    ) -> WorldEvent:
        data: dict[str, object] = {
            "person_count": observation.person_count,
        }
        if observation.nearest_person_distance_m is not None:
            data["distance_m"] = observation.nearest_person_distance_m
        if observation.confidence is not None:
            data["confidence"] = observation.confidence
        return WorldEvent(
            type=event_type,
            timestamp_s=observation.observed_at_s,
            entity_id="nearest_person",
            data=data,
        )

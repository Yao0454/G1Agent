"""Minimal state needed to avoid greeting the same visible person every frame."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PerceptionResult


@dataclass(slots=True)
class WorldState:
    absence_reset_s: float = 2.0

    person_visible: bool = False
    person_greeted: bool = False
    person_too_close: bool = False
    nearest_person_distance_m: float | None = None
    last_seen_at_s: float | None = None
    last_observed_at_s: float | None = None

    def __post_init__(self) -> None:
        if self.absence_reset_s <= 0:
            raise ValueError("absence_reset_s must be greater than zero")

    def observe(self, result: PerceptionResult) -> None:
        if (
            self.last_observed_at_s is not None
            and result.observed_at_s < self.last_observed_at_s
        ):
            raise ValueError("perception observations must be time ordered")
        self.last_observed_at_s = result.observed_at_s

        if result.person_detected:
            if not self.person_visible:
                self.person_greeted = False
            self.person_visible = True
            self.nearest_person_distance_m = result.nearest_person_distance_m
            self.last_seen_at_s = result.observed_at_s
            return

        if self.last_seen_at_s is None:
            return
        if result.observed_at_s - self.last_seen_at_s >= self.absence_reset_s:
            self.person_visible = False
            self.person_greeted = False
            self.person_too_close = False
            self.nearest_person_distance_m = None

    def mark_greeted(self) -> None:
        if not self.person_visible:
            raise RuntimeError("cannot mark an absent person as greeted")
        self.person_greeted = True

    def to_dict(self) -> dict[str, object]:
        return {
            "person_visible": self.person_visible,
            "person_greeted": self.person_greeted,
            "person_too_close": self.person_too_close,
            "nearest_person_distance_m": self.nearest_person_distance_m,
            "last_seen_at_s": self.last_seen_at_s,
            "last_observed_at_s": self.last_observed_at_s,
        }

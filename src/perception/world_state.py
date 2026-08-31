"""Minimal state needed to avoid greeting the same visible person every frame."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PerceptionResult


@dataclass(slots=True)
class WorldState:
    absence_reset_s: float = 2.0
    greeting_retry_s: float = 5.0

    person_visible: bool = False
    person_greeted: bool = False
    last_seen_at_s: float | None = None
    last_observed_at_s: float | None = None
    last_greeting_attempt_at_s: float | None = None

    def __post_init__(self) -> None:
        if self.absence_reset_s <= 0:
            raise ValueError("absence_reset_s must be greater than zero")
        if self.greeting_retry_s < 0:
            raise ValueError("greeting_retry_s must not be negative")

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
                self.last_greeting_attempt_at_s = None
            self.person_visible = True
            self.last_seen_at_s = result.observed_at_s
            return

        if self.last_seen_at_s is None:
            return
        if result.observed_at_s - self.last_seen_at_s >= self.absence_reset_s:
            self.person_visible = False
            self.person_greeted = False
            self.last_greeting_attempt_at_s = None

    def should_greet(self, observed_at_s: float) -> bool:
        if not self.person_visible or self.person_greeted:
            return False
        if self.last_greeting_attempt_at_s is None:
            return True
        return (
            observed_at_s - self.last_greeting_attempt_at_s
            >= self.greeting_retry_s
        )

    def mark_greeting_attempt(self, observed_at_s: float) -> None:
        if not self.person_visible:
            raise RuntimeError("cannot greet when no person is visible")
        self.last_greeting_attempt_at_s = observed_at_s

    def mark_greeted(self) -> None:
        if not self.person_visible:
            raise RuntimeError("cannot mark an absent person as greeted")
        self.person_greeted = True

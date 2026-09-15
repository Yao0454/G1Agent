from __future__ import annotations

import time
import unittest

from pydantic import ValidationError

from agent import TemporalVisionState, TemporalVisionStateUpdate


class TemporalVisionStateTests(unittest.TestCase):
    def test_partial_update_preserves_existing_memory(self) -> None:
        state = TemporalVisionState(
            scene_summary="一名访客站在机器人前方",
            interaction_state="访客已经挥过手",
            updated_at_s=10.0,
        )

        updated = state.apply(
            TemporalVisionStateUpdate(human_intent="继续与机器人互动"),
            updated_at_s=12.0,
        )

        self.assertEqual(updated.scene_summary, state.scene_summary)
        self.assertEqual(updated.interaction_state, state.interaction_state)
        self.assertEqual(updated.human_intent, "继续与机器人互动")
        self.assertEqual(updated.updated_at_s, 12.0)

    def test_empty_update_does_not_refresh_memory_timestamp(self) -> None:
        state = TemporalVisionState(updated_at_s=10.0)

        self.assertIs(state.apply(TemporalVisionStateUpdate()), state)

    def test_runtime_records_action_and_model_cannot_supply_it(self) -> None:
        state = TemporalVisionState().record_action(
            "execute_skill:wave",
            updated_at_s=5.0,
        )

        self.assertEqual(state.last_action, "execute_skill:wave")
        self.assertEqual(state.updated_at_s, 5.0)
        with self.assertRaises(ValidationError):
            TemporalVisionStateUpdate.model_validate(
                {"last_action": "execute_skill:move_forward"}
            )

    def test_context_reports_local_age_without_changing_state(self) -> None:
        state = TemporalVisionState(scene_summary="场景", updated_at_s=10.0)

        context = state.to_context(now_s=12.25)

        self.assertEqual(context["age_s"], 2.25)
        self.assertEqual(state.updated_at_s, 10.0)

    def test_text_fields_are_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            TemporalVisionStateUpdate(scene_summary="x" * 601)

        state = TemporalVisionState().record_action(
            "x" * 200, updated_at_s=time.monotonic()
        )
        self.assertEqual(len(state.last_action or ""), 160)


if __name__ == "__main__":
    unittest.main()

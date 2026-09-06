from __future__ import annotations

import unittest

from agent.decision import DecisionAgentError
from agent.social_vision import SocialVisionAgent
from robot import RobotState
from skills.motions import HandshakeSkill, WaveSkill
from skills import build_g1_autonomy_skills
from tests.test_vision_policy import FakeVisionInvoker, camera_frame


class SocialVisionTests(unittest.IsolatedAsyncioTestCase):
    async def decide(self, **changes):
        payload = dict(
            gesture="handshake", hand_visible=True, directed_at_robot=True,
            present_in_latest=True, evidence="offered_hand",
        )
        payload.update(changes)
        invoker = FakeVisionInvoker([payload])
        decision = await SocialVisionAgent(invoker=invoker).decide(
            [camera_frame(1), camera_frame(1.4), camera_frame(1.8)],
            RobotState(hardware=False, connected=True),
            [HandshakeSkill(), WaveSkill()],
        )
        return decision, invoker

    async def test_handshake_with_visible_evidence(self):
        decision, invoker = await self.decide()
        self.assertEqual(decision.skill, "handshake")
        self.assertEqual(decision.arguments, {})
        self.assertIn("[-0.8, -0.4, 0.0]", invoker.calls[0][1])
        self.assertNotIn("argument_defaults", invoker.calls[0][1])

    async def test_wave_requires_motion_evidence(self):
        decision, _ = await self.decide(gesture="wave", evidence="side_to_side")
        self.assertEqual(decision.skill, "wave")

    async def test_ambiguous_or_absent_evidence_does_not_execute(self):
        for changes in (
            {"hand_visible": False}, {"directed_at_robot": False},
            {"present_in_latest": False}, {"evidence": "raised_palm"},
            {"gesture": "uncertain"}, {"gesture": "none"},
            {"gesture": "high_five", "evidence": "raised_palm"},
        ):
            with self.subTest(changes=changes):
                decision, _ = await self.decide(**changes)
                self.assertEqual(decision.action, "ignore")

    async def test_strict_schema_rejects_schema_copy_and_extra_fields(self):
        for changes in (
            {"hand_visible": "true"}, {"arguments": {}},
            {"gesture": {"type": "string"}},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(DecisionAgentError):
                    await self.decide(**changes)

    async def test_truncated_json_does_not_execute(self):
        agent = SocialVisionAgent(invoker=FakeVisionInvoker(['{"gesture":"handshake"']))
        with self.assertRaises(DecisionAgentError):
            await agent.decide(
                [camera_frame(1), camera_frame(2)],
                RobotState(hardware=False, connected=True), [HandshakeSkill()],
            )

    async def test_single_frame_waits_without_inference(self):
        invoker = FakeVisionInvoker([])
        decision = await SocialVisionAgent(invoker=invoker).decide(
            [camera_frame(1)], RobotState(hardware=False, connected=True), [],
        )
        self.assertEqual(decision.action, "ignore")
        self.assertFalse(invoker.calls)

    async def test_high_five_and_active_handshake(self):
        for gesture, evidence, context, expected in (
            ("high_five", "raised_palm", {}, "execute_skill"),
            ("handshake", "offered_hand", {"active_skill": "handshake"}, "continue"),
        ):
            agent = SocialVisionAgent(invoker=FakeVisionInvoker([dict(
                gesture=gesture, evidence=evidence, hand_visible=True,
                directed_at_robot=True, present_in_latest=True,
            )]))
            decision = await agent.decide(
                [camera_frame(1), camera_frame(2)],
                RobotState(hardware=False, connected=True),
                build_g1_autonomy_skills(), policy_context=context,
            )
            self.assertEqual(decision.action, expected)
            self.assertEqual(agent.last_metrics["gesture_observation"]["gesture"], gesture)

    async def test_duplicate_frame_timestamps_are_rejected(self):
        invoker = FakeVisionInvoker([])
        decision = await SocialVisionAgent(invoker=invoker).decide(
            [camera_frame(1), camera_frame(1)],
            RobotState(hardware=False, connected=True), [HandshakeSkill()],
        )
        self.assertEqual(decision.action, "ignore")
        self.assertFalse(invoker.calls)

from __future__ import annotations

import asyncio
import unittest

from g1agent.brain import OllamaBrain, RobotResponse
from g1agent.robot import Robot


class DemoTests(unittest.TestCase):
    def test_parse_response_restricts_action(self) -> None:
        response = OllamaBrain._parse_response('{"speech":"好","action":"not_allowed"}')
        self.assertEqual(response, RobotResponse(speech="好", action="none"))
        self.assertEqual(response["speech"], "好")

    def test_parse_response_accepts_markdown_fence(self) -> None:
        response = OllamaBrain._parse_response(
            '```json\n{"speech":"大家好","action":"wave"}\n```'
        )
        self.assertEqual(response.speech, "大家好")
        self.assertEqual(response.action, "wave")

    def test_ollama_url_normalization(self) -> None:
        self.assertEqual(
            OllamaBrain._chat_url("127.0.0.1:11434"),
            "http://127.0.0.1:11434/api/chat",
        )

    def test_fallback_selects_action(self) -> None:
        response = OllamaBrain._fallback("请向大家挥手")
        self.assertEqual(response.action, "wave")
        self.assertTrue(response.used_fallback)

    def test_fallback_selects_handshake(self) -> None:
        response = OllamaBrain._fallback("能跟我握手吗")
        self.assertEqual(response.action, "shake_hand")

    def test_explicit_handshake_overrides_nearby_action(self) -> None:
        response = OllamaBrain._apply_explicit_overrides(
            "能跟我握手吗", RobotResponse(speech="好的", action="wave")
        )
        self.assertEqual(response.action, "shake_hand")

    def test_robot_dry_run_is_safe(self) -> None:
        result = asyncio.run(Robot().execute("wave"))
        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "dry-run")

    def test_robot_rejects_unknown_action(self) -> None:
        result = asyncio.run(Robot().execute("set_joint_torque"))
        self.assertFalse(result.ok)

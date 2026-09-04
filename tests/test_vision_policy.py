from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import Sequence

from agent import (
    AgentDecision,
    VisionDecisionAgent,
    VisionPolicyDecision,
    VisionPolicyWorker,
)
from core.runtime import SkillRuntime
from perception import CameraFrame, PerceptionResult, VideoBuffer
from robot import RobotState, SimulatedRobotAdapter
from skills.motions import MoveBackwardSkill, WaveSkill


def camera_frame(at_s: float) -> CameraFrame:
    observation = PerceptionResult(observed_at_s=at_s, source="camera:test")
    return CameraFrame(
        observed_at_s=at_s,
        rgb=b"jpeg",
        depth=None,
        observation=observation,
        nearest_obstacle_distance_m=2.0,
    )


class FakeVisionInvoker:
    def __init__(self, responses: Sequence[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[Sequence[object], str]] = []

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        self.calls.append((frames, prompt))
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class VideoBufferTests(unittest.TestCase):
    def test_window_evicts_old_frames_and_samples_endpoints(self) -> None:
        buffer = VideoBuffer(window_s=2.0, max_frames=60)
        for index in range(6):
            buffer.push(camera_frame(float(index)))

        sampled = buffer.sample(3)

        self.assertEqual([frame.observed_at_s for frame in sampled], [3.0, 4.0, 5.0])

    def test_uniform_sample_includes_first_and_latest_frame(self) -> None:
        buffer = VideoBuffer(window_s=10.0, max_frames=60)
        for index in range(10):
            buffer.push(camera_frame(float(index)))

        sampled = buffer.sample(4)

        self.assertEqual([frame.observed_at_s for frame in sampled], [0.0, 3.0, 6.0, 9.0])


class VisionDecisionAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_frames_and_runtime_context_produce_agent_decision(self) -> None:
        invoker = FakeVisionInvoker(
            [
                json.dumps(
                    {
                        "action": "execute_skill",
                        "skill": "wave",
                        "arguments": {"arm": "right"},
                        "speech": None,
                        "reason": "person approached",
                    }
                )
            ]
        )
        runtime = SkillRuntime(SimulatedRobotAdapter())
        runtime.register(WaveSkill())
        agent = VisionDecisionAgent(invoker=invoker)

        decision = await agent.decide(
            [camera_frame(1.0), camera_frame(2.0)],
            RobotState(hardware=False, connected=True),
            runtime.registry.list(),
        )

        self.assertEqual(decision.skill, "wave")
        self.assertEqual(len(invoker.calls[0][0]), 2)
        self.assertIn('"frame_count": 2', invoker.calls[0][1])
        self.assertIn('"name": "wave"', invoker.calls[0][1])

    async def test_continue_and_interrupt_are_valid_noop_decisions(self) -> None:
        for action in ("continue", "interrupt"):
            decision = AgentDecision(action=action)
            self.assertEqual(decision.action, action)

    async def test_policy_decision_serializes_window_state_and_metrics(self) -> None:
        payload = VisionPolicyDecision(
            decided_at_s=3.0,
            frame_count=2,
            window_start_s=1.0,
            window_end_s=2.0,
            decision=AgentDecision(action="ignore"),
            robot_state=RobotState(hardware=False, connected=True),
            model_metrics={"inference_s": 0.25},
        ).to_dict()

        self.assertEqual(payload["frame_count"], 2)
        self.assertEqual(payload["window_start_s"], 1.0)
        self.assertEqual(
            payload["decision"],
            AgentDecision(action="ignore").to_dict(),
        )
        self.assertEqual(payload["model_metrics"], {"inference_s": 0.25})

    async def test_malformed_ignore_is_recovered_as_safe_noop(self) -> None:
        decision = VisionDecisionAgent._parse_output(
            '{"action":"ignore","skill":null,"arguments":{"bad":'
        )

        self.assertEqual(decision.action, "ignore")
        self.assertEqual(decision.arguments, {})

    async def test_malformed_execute_decision_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "JSON object"):
            VisionDecisionAgent._parse_output(
                '{"action":"execute_skill","skill":"wave"'
            )

    async def test_noisy_json_noop_discards_hallucinated_arguments(self) -> None:
        decision = VisionDecisionAgent._parse_output(
            json.dumps(
                {
                    "action": "ignore",
                    "skill": None,
                    "arguments": {"skill_catalog": {"wave": "definition"}},
                    "speech": None,
                    "reason": "nothing actionable",
                }
            )
        )

        self.assertEqual(decision.action, "ignore")
        self.assertEqual(decision.arguments, {})

    async def test_noisy_mapping_continue_discards_hallucinated_arguments(self) -> None:
        decision = VisionDecisionAgent._parse_output(
            {
                "structured_response": {
                    "action": " continue ",
                    "skill": " ",
                    "arguments": {"distance_m": 0.2},
                    "speech": "",
                }
            }
        )

        self.assertEqual(decision.action, "continue")
        self.assertIsNone(decision.skill)
        self.assertEqual(decision.arguments, {})
        self.assertIsNone(decision.speech)

    async def test_noisy_interrupt_remains_strictly_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "requires a skill"):
            VisionDecisionAgent._parse_output(
                {
                    "action": "interrupt",
                    "skill": None,
                    "arguments": {"distance_m": 0.2},
                    "speech": None,
                }
            )


class VisionPolicyWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_depth_safety_latch_blocks_skill_execution(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        buffer = VideoBuffer(window_s=2.0, max_frames=60)
        buffer.push(camera_frame(1.0))
        invoker = FakeVisionInvoker(
            [
                {
                    "action": "execute_skill",
                    "skill": "wave",
                    "arguments": {"arm": "right"},
                }
            ]
        )
        worker = VisionPolicyWorker(
            runtime,
            VisionDecisionAgent(invoker=invoker),
            buffer,
            interval_s=0.01,
        )
        worker.set_safety_latched(True)

        await worker.start()
        try:
            await asyncio.sleep(0.04)
        finally:
            await worker.stop()

        self.assertNotIn(("wave", "right"), robot.events)
        self.assertTrue(
            any(
                outcome.suppressed_reason == "depth safety latch is active"
                for outcome in worker.drain_outcomes()
            )
        )

    async def test_identical_skill_is_suppressed_during_cooldown(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        buffer = VideoBuffer(window_s=2.0, max_frames=60)
        buffer.push(camera_frame(1.0))
        invoker = FakeVisionInvoker(
            [
                {
                    "action": "execute_skill",
                    "skill": "wave",
                    "arguments": {"arm": "right"},
                }
            ]
        )
        worker = VisionPolicyWorker(
            runtime,
            VisionDecisionAgent(invoker=invoker),
            buffer,
            interval_s=0.01,
            action_cooldown_s=10.0,
        )

        await worker.start()
        try:
            await asyncio.sleep(0.08)
        finally:
            await worker.stop()

        self.assertEqual(robot.events.count(("wave", "right")), 1)
        self.assertTrue(
            any(
                outcome.suppressed_reason == "identical behavior is in cooldown"
                for outcome in worker.drain_outcomes()
            )
        )

    async def test_interrupt_cancels_active_skill_and_stops_robot(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(MoveBackwardSkill())
        buffer = VideoBuffer(window_s=2.0, max_frames=60)
        buffer.push(camera_frame(1.0))
        invoker = FakeVisionInvoker(
            [
                {
                    "action": "execute_skill",
                    "skill": "move_backward",
                    "arguments": {"distance_m": 0.3},
                },
                {"action": "interrupt", "reason": "path blocked"},
                {"action": "continue"},
            ]
        )
        worker = VisionPolicyWorker(
            runtime,
            VisionDecisionAgent(invoker=invoker),
            buffer,
            interval_s=0.01,
        )

        await worker.start()
        try:
            await asyncio.sleep(0.08)
        finally:
            await worker.stop()

        self.assertIn("move_velocity", [event[0] for event in robot.events])
        self.assertIn(("stop", None), robot.events)


if __name__ == "__main__":
    unittest.main()

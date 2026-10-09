import asyncio
import base64
import json
import time
import unittest

import httpx

from adapters.langchain import build_langchain_tools
from agent.decision import DecisionAgentError
from agent.remote_vision import REMOTE_VISION_MODEL, RemoteVisionInvoker
from agent.vision_policy import (
    VisionDecisionAgent,
    VisionPolicyWorker,
    _skill_catalog_payload,
    _VisionDecisionRequest,
)
from core.runtime import SkillRuntime
from perception import CameraFrame, PerceptionResult, VideoBuffer
from robot import RobotState, SimulatedRobotAdapter
from skills import build_g1_all_skills, register_g1_skills


class RemoteVisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_registered_skill_can_pass_visual_dispatch(self):
        """Exercise all 52 real skill implementations with a simulated robot."""
        arguments = {
            "handshake": {"duration_s": 1},
            "shake_hand": {"duration_s": 1},
            "continuous_gait": {"enabled": False},
            "switch_move_mode": {"enabled": False},
            "set_speed_mode": {"mode": 1},
            "set_fsm_id": {"fsm_id": 500},
            "set_balance_mode": {"balance_mode": 0},
            "set_swing_height": {"swing_height": 0.1},
            "set_stand_height": {"stand_height": 0.7},
            "set_velocity": {"vx": 0, "vy": 0, "omega": 0},
            "move_sdk": {"vx": 0, "vy": 0, "vyaw": 0},
            "set_task_id": {"task_id": 0},
            "switch_to_internal_ctrl": {"mode": "last"},
            "fsm_api": {"parameter": "{}"},
            "execute_custom_arm_action": {"action_name": "test-action"},
        }
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        register_g1_skills(runtime)
        selected = None

        def handle(request):
            payload = json.loads(request.content)
            context = payload["prompt"].split("Runtime context:\n", 1)[1]
            context, _ = json.JSONDecoder().raw_decode(context)
            self.assertEqual(
                {s["name"] for s in context["skill_catalog"]},
                {s.metadata.name for s in runtime.registry.list()},
            )
            return httpx.Response(
                200,
                json={
                    "request_id": payload["request_id"],
                    "output": json.dumps(
                        {
                            "decision": {
                                "action": "execute_skill",
                                "skill": selected,
                                "arguments": arguments.get(selected, {}),
                            },
                            "state_update": {},
                        }
                    ),
                },
            )

        agent = VisionDecisionAgent(
            invoker=RemoteVisionInvoker(transport=httpx.MockTransport(handle))
        )
        worker = VisionPolicyWorker(
            runtime, agent, VideoBuffer(), action_cooldown_s=0, max_decision_age_s=5
        )
        execution = asyncio.create_task(worker._execution_loop())
        try:
            for skill in runtime.registry.list():
                selected = skill.metadata.name
                with self.subTest(skill=selected):
                    now = time.monotonic()
                    frame = CameraFrame(now, b"jpeg", None, PerceptionResult(now))
                    state = await robot.get_state()
                    decision = await agent.decide(
                        [frame], state, runtime.registry.list()
                    )
                    await worker._decision_queue.put(
                        _VisionDecisionRequest(decision, (frame,), state, selected, {})
                    )
                    outcome = await asyncio.wait_for(worker._outcome_queue.get(), 3)
                    self.assertTrue(outcome.executed, outcome.suppressed_reason)
                    self.assertIsNotNone(outcome.skill_result)
                    self.assertTrue(
                        outcome.skill_result.success, outcome.skill_result.message
                    )
                    self.assertFalse(worker.drain_errors())
        finally:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            await worker.stop()
            await agent.close()

    async def test_complete_catalog_reaches_text_and_visual_agents_and_executes(self):
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        register_g1_skills(runtime)
        expected = {s.metadata.name for s in build_g1_all_skills()}
        self.assertEqual({t.name for t in build_langchain_tools(runtime)}, expected)
        catalog = _skill_catalog_payload(runtime.registry.list())
        self.assertEqual({s["name"] for s in catalog}, expected)
        fsm = next(s for s in catalog if s["name"] == "set_fsm_id")
        self.assertIn("fsm_id", fsm["arguments_schema"]["properties"])

        def handle(request):
            if request.url.path == "/health":
                return httpx.Response(
                    200, json={"status": "ready", "model": REMOTE_VISION_MODEL}
                )
            self.assertEqual(request.url.path, "/v1/vision/invoke")
            payload = json.loads(request.content)
            self.assertEqual(base64.b64decode(payload["frames"][0]), b"jpeg")
            self.assertEqual(payload["model"], REMOTE_VISION_MODEL)
            self.assertIn("set_fsm_id", payload["prompt"])
            self.assertIn("Do not wrap it in decision or add state_update", payload["prompt"])
            return httpx.Response(
                200,
                json={
                    "request_id": payload["request_id"],
                    "output": json.dumps(
                        {
                            "action": "execute_skill",
                            "skill": "set_fsm_id",
                            "arguments": {"fsm_id": 500},
                        }
                    ),
                    "metrics": {"inference_s": 0.1, "generated_tokens": 40},
                },
            )

        invoker = RemoteVisionInvoker(transport=httpx.MockTransport(handle))
        agent = VisionDecisionAgent(invoker=invoker)
        now = time.monotonic()
        frame = CameraFrame(now, b"jpeg", None, PerceptionResult(now))
        worker = VisionPolicyWorker(runtime, agent, VideoBuffer())
        try:
            await agent.warmup()
            decision = await agent.decide(
                [frame], RobotState(False, True), runtime.registry.list()
            )
            result, spoken = await worker._execute(decision)
            self.assertTrue(result.success)
            self.assertFalse(spoken)
            self.assertIn(
                ("loco_action", ("set_fsm_id", {"fsm_id": 500})), robot.events
            )
            rejected = await runtime.execute("set_fsm_id", fsm_id=-1)
            self.assertFalse(rejected.success)
            self.assertEqual(len(robot.events), 1)
        finally:
            await agent.close()

    async def test_compact_response_keeps_runtime_action_history(self):
        prompts = []

        def handle(request):
            payload = json.loads(request.content)
            prompts.append(payload["prompt"])
            return httpx.Response(200, json={
                "request_id": payload["request_id"],
                "output": '{"action":"execute_skill","skill":"clap"}'
                if len(prompts) == 1 else '{"action":"ignore"}',
            })

        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        register_g1_skills(runtime)
        agent = VisionDecisionAgent(invoker=RemoteVisionInvoker(
            transport=httpx.MockTransport(handle)))
        now = time.monotonic()
        frame = CameraFrame(now, b"jpeg", None, PerceptionResult(now))
        try:
            first = await agent.decide([frame], await robot.get_state(), runtime.registry.list())
            result = await runtime.execute(first.skill, **first.arguments)
            self.assertTrue(result.success)
            agent.record_action(first)
            second = await agent.decide([frame], await robot.get_state(), runtime.registry.list())
            context = prompts[1].split("Runtime context:\n", 1)[1]
            context, _ = json.JSONDecoder().raw_decode(context)
            self.assertEqual(context["temporal_vision_state"]["last_action"], "execute_skill:clap")
            self.assertEqual(second.action, "ignore")
        finally:
            await agent.close()

    async def test_invalid_remote_responses_are_rejected(self):
        for response in [
            {"request_id": 99, "output": "{}"},
            {"request_id": 1, "output": ""},
            {"request_id": 1, "output": "{}", "metrics": {"generated_tokens": 256}},
        ]:
            with self.subTest(response=response):
                invoker = RemoteVisionInvoker(
                    transport=httpx.MockTransport(
                        lambda request, response=response: httpx.Response(
                            200, json=response
                        )
                    )
                )
                try:
                    with self.assertRaises(DecisionAgentError):
                        await invoker.ainvoke([b"jpeg"], "test")
                finally:
                    await invoker.close()

    async def test_cancellation_propagates_to_pending_request(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def handle(request):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        invoker = RemoteVisionInvoker(transport=httpx.MockTransport(handle))
        task = asyncio.create_task(invoker.ainvoke([b"jpeg"], "test"))
        try:
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cancelled.is_set())
        finally:
            await invoker.close()

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.registry import SkillRegistry
from core.runtime import SkillRuntime
from core.skill import RobotSkill
from core.types import FailureCode, SkillStatus
from robot.base import ActionVerification, RobotCommandError, RobotState
from robot.unitree_adapter import (
    UnitreeBindings,
    UnitreeG1Adapter,
    UnitreeG1Config,
)
from skills.motions import MoveBackwardSkill, WaveSkill


class FakeRobotAdapter:
    def __init__(
        self,
        *,
        hardware: bool = False,
        connected: bool = False,
        wave_error: bool = False,
        move_error: bool = False,
        wave_verification: ActionVerification | None = None,
    ) -> None:
        self.hardware = hardware
        self.connected = connected
        self.wave_error = wave_error
        self.move_error = move_error
        self.wave_verification = wave_verification or ActionVerification(
            completed=True,
            observable=True,
            message="wave completion verified",
            details={"method": "fake"},
        )
        self.waves: list[str] = []
        self.velocity_commands: list[tuple[float, float, float]] = []
        self.stop_count = 0

    async def get_state(self) -> RobotState:
        return RobotState(hardware=self.hardware, connected=self.connected)

    async def stop(self) -> None:
        self.stop_count += 1

    async def wave(self, arm: str) -> None:
        if self.wave_error:
            raise RobotCommandError("wave command rejected")
        self.waves.append(arm)

    async def wait_for_wave_completion(
        self,
        arm: str,
        timeout_s: float,
    ) -> ActionVerification:
        return self.wave_verification

    async def move_velocity(
        self,
        forward_m_s: float,
        lateral_m_s: float,
        yaw_rad_s: float,
    ) -> None:
        self.velocity_commands.append(
            (forward_m_s, lateral_m_s, yaw_rad_s)
        )
        if self.move_error:
            raise RobotCommandError("move command rejected")


class EmptyArgs(SkillArgs):
    pass


class SlowSkill(RobotSkill[EmptyArgs]):
    metadata = SkillMetadata(
        name="slow",
        description="A skill used to verify timeouts.",
        timeout_s=0.01,
    )
    args_model = EmptyArgs

    async def execute(self, ctx: SkillContext, args: EmptyArgs) -> SkillResult:
        await asyncio.sleep(1)
        return SkillResult.ok()


class ResourceSkill(RobotSkill[EmptyArgs]):
    metadata = SkillMetadata(
        name="resource_skill",
        description="A skill used to verify resource locking.",
        required_resources=("shared_resource",),
        timeout_s=1.0,
    )
    args_model = EmptyArgs

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.execution_count = 0

    async def execute(self, ctx: SkillContext, args: EmptyArgs) -> SkillResult:
        self.execution_count += 1
        self.started.set()
        await self.release.wait()
        return SkillResult.ok()


class VerificationSkill(RobotSkill[EmptyArgs]):
    metadata = SkillMetadata(
        name="verification_skill",
        description="A skill used to verify lifecycle ordering.",
        timeout_s=0.05,
    )
    args_model = EmptyArgs

    def __init__(self, *, block_verification: bool = False) -> None:
        self.block_verification = block_verification
        self.phases: list[str] = []

    async def execute(self, ctx: SkillContext, args: EmptyArgs) -> SkillResult:
        self.phases.append("execute")
        return SkillResult.ok("command accepted")

    async def verify(
        self,
        ctx: SkillContext,
        args: EmptyArgs,
        result: SkillResult,
    ) -> SkillResult:
        self.phases.append("verify")
        if self.block_verification:
            await asyncio.sleep(1)
        result.verification = {"completed": True}
        return result

    async def cleanup(self, ctx: SkillContext, args: EmptyArgs) -> None:
        self.phases.append("cleanup")


class SkillRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_wave_runs_through_runtime(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave", arm="right")

        self.assertTrue(result.success)
        self.assertEqual(result.status, SkillStatus.SUCCEEDED)
        self.assertEqual(
            result.data,
            {"arm": "right", "command_accepted": True},
        )
        self.assertEqual(
            result.verification,
            {"observable": True, "completed": True, "method": "fake"},
        )
        self.assertEqual(robot.waves, ["right"])
        self.assertIsNotNone(result.duration_s)

    async def test_wave_rejects_unsupported_arm(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave", arm="left")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, FailureCode.INVALID_ARGUMENTS)
        self.assertEqual(robot.waves, [])

    async def test_wave_requires_connected_hardware(self) -> None:
        robot = FakeRobotAdapter(hardware=True, connected=False)
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave")

        self.assertEqual(result.status, SkillStatus.PRECONDITION_FAILED)
        self.assertEqual(result.failure_code, FailureCode.PRECONDITION_NOT_MET)
        self.assertEqual(robot.waves, [])

    async def test_robot_error_is_structured_without_implicit_stop(self) -> None:
        robot = FakeRobotAdapter(wave_error=True)
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave")

        self.assertEqual(result.failure_code, FailureCode.ROBOT_ERROR)
        self.assertEqual(robot.stop_count, 0)

    async def test_wave_requires_observed_completion(self) -> None:
        robot = FakeRobotAdapter(
            wave_verification=ActionVerification(
                completed=False,
                observable=True,
                message="wave completion feedback timed out",
                details={"wave_observed": True},
            )
        )
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave")

        self.assertFalse(result.success)
        self.assertEqual(result.status, SkillStatus.VERIFICATION_FAILED)
        self.assertEqual(result.failure_code, FailureCode.VERIFICATION_FAILED)
        self.assertTrue(result.verification["wave_observed"])

    async def test_verify_runs_before_cleanup(self) -> None:
        runtime = SkillRuntime(FakeRobotAdapter())
        skill = VerificationSkill()
        runtime.register(skill)

        result = await runtime.execute("verification_skill")

        self.assertTrue(result.success)
        self.assertEqual(result.verification, {"completed": True})
        self.assertEqual(skill.phases, ["execute", "verify", "cleanup"])

    async def test_verification_uses_skill_execution_timeout(self) -> None:
        runtime = SkillRuntime(FakeRobotAdapter())
        skill = VerificationSkill(block_verification=True)
        runtime.register(skill)

        result = await runtime.execute("verification_skill")

        self.assertEqual(result.status, SkillStatus.TIMEOUT)
        self.assertEqual(skill.phases, ["execute", "verify", "cleanup"])

    async def test_unknown_skill_returns_structured_failure(self) -> None:
        runtime = SkillRuntime(FakeRobotAdapter())

        result = await runtime.execute("missing")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, FailureCode.INVALID_ARGUMENTS)

    async def test_timeout_does_not_assume_a_stop_policy(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(SlowSkill())

        result = await runtime.execute("slow")

        self.assertEqual(result.status, SkillStatus.TIMEOUT)
        self.assertEqual(robot.stop_count, 0)

    async def test_move_backward_is_bounded_and_always_stops(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(MoveBackwardSkill())

        with patch(
            "skills.motions.move_backward.asyncio.sleep",
            new=AsyncMock(),
        ):
            result = await runtime.execute(
                "move_backward",
                distance_m=0.2,
            )

        self.assertTrue(result.success)
        self.assertEqual(robot.velocity_commands, [(-0.2, 0.0, 0.0)])
        self.assertEqual(robot.stop_count, 1)

    async def test_move_backward_stops_after_command_error(self) -> None:
        robot = FakeRobotAdapter(move_error=True)
        runtime = SkillRuntime(robot)
        runtime.register(MoveBackwardSkill())

        result = await runtime.execute("move_backward")

        self.assertEqual(result.failure_code, FailureCode.ROBOT_ERROR)
        self.assertEqual(robot.stop_count, 1)

    async def test_move_backward_rejects_unsafe_distance(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(MoveBackwardSkill())

        result = await runtime.execute("move_backward", distance_m=2.0)

        self.assertEqual(result.failure_code, FailureCode.INVALID_ARGUMENTS)
        self.assertEqual(robot.velocity_commands, [])
        self.assertEqual(robot.stop_count, 0)

    async def test_required_resources_serialize_concurrent_invocations(self) -> None:
        runtime = SkillRuntime(FakeRobotAdapter())
        skill = ResourceSkill()
        runtime.register(skill)

        first = asyncio.create_task(runtime.execute("resource_skill"))
        await asyncio.wait_for(skill.started.wait(), timeout=0.2)
        second = asyncio.create_task(runtime.execute("resource_skill"))
        await asyncio.sleep(0)
        self.assertEqual(skill.execution_count, 1)

        skill.release.set()
        first_result, second_result = await asyncio.gather(first, second)
        self.assertTrue(first_result.success)
        self.assertTrue(second_result.success)
        self.assertEqual(skill.execution_count, 2)

    def test_registry_rejects_duplicate_names(self) -> None:
        registry = SkillRegistry()
        registry.register(WaveSkill())

        with self.assertRaisesRegex(ValueError, "duplicate skill"):
            registry.register(WaveSkill())


class FakeChannel:
    def __init__(self) -> None:
        self.initialize_calls: list[tuple[int, str]] = []
        self.release_count = 0

    def initialize(
        self,
        domain_id: int = 0,
        network_interface: str = "",
    ) -> None:
        self.initialize_calls.append((domain_id, network_interface))

    def release(self) -> None:
        self.release_count += 1


class FakeLocoClient:
    def __init__(self) -> None:
        self.timeout_s: float | None = None
        self.init_count = 0
        self.init_error: RuntimeError | None = None
        self.fsm_status = 0
        self.fsm_id = 500
        self.wave_status = 0
        self.wave_flags: list[bool] = []
        self.stop_status = 0
        self.stop_count = 0
        self.move_status = 0
        self.move_calls: list[tuple[float, float, float, bool]] = []

    def set_timeout(self, seconds: float) -> None:
        self.timeout_s = seconds

    def init(self) -> None:
        self.init_count += 1
        if self.init_error is not None:
            raise self.init_error

    def get_fsm_id(self) -> tuple[int, int]:
        return self.fsm_status, self.fsm_id

    def wave_hand(self, turn_flag: bool = False) -> int:
        self.wave_flags.append(turn_flag)
        return self.wave_status

    def stop_move(self) -> int:
        self.stop_count += 1
        return self.stop_status

    def move(
        self,
        vx: float,
        vy: float,
        vyaw: float,
        continous_move: bool,
    ) -> int:
        self.move_calls.append((vx, vy, vyaw, continous_move))
        return self.move_status


class FakeArmActionClient:
    def __init__(self) -> None:
        self.timeout_s: float | None = None
        self.init_count = 0
        self.action_ids: list[int] = []
        self.action_status = 0
        self.on_execute: Callable[[int], None] | None = None

    def set_timeout(self, seconds: float) -> None:
        self.timeout_s = seconds

    def init(self) -> None:
        self.init_count += 1

    def execute_action(self, action_id: int) -> int:
        self.action_ids.append(action_id)
        if self.action_status == 0 and self.on_execute is not None:
            self.on_execute(action_id)
        return self.action_status


class FakeArmActionMonitor:
    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback
        self.init_count = 0
        self.close_count = 0

    def init_channel(self) -> None:
        self.init_count += 1

    def close_channel(self) -> None:
        self.close_count += 1

    def emit(self, payload: str) -> None:
        self.callback(payload)


class UnitreeG1AdapterTests(unittest.IsolatedAsyncioTestCase):
    def build_adapter(
        self,
        channel: FakeChannel,
        client: FakeLocoClient,
    ) -> UnitreeG1Adapter:
        return UnitreeG1Adapter(
            UnitreeG1Config(
                network_interface="eth0",
                domain_id=7,
                timeout_s=4.0,
            ),
            bindings=UnitreeBindings(
                channel=channel,
                create_loco_client=lambda: client,
            ),
        )

    async def test_legacy_wave_is_not_completed_without_feedback(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave", arm="right")
        state = await adapter.get_state()
        await adapter.close()

        self.assertFalse(result.success)
        self.assertEqual(result.status, SkillStatus.VERIFICATION_FAILED)
        self.assertFalse(result.verification["observable"])
        self.assertEqual(channel.initialize_calls, [(7, "eth0")])
        self.assertEqual(channel.release_count, 1)
        self.assertEqual(client.timeout_s, 4.0)
        self.assertEqual(client.init_count, 1)
        self.assertEqual(client.wave_flags, [False])
        self.assertEqual(client.stop_count, 0)
        self.assertEqual(state.details, {"fsm_id": 500})
        self.assertFalse(adapter.connected)

    async def test_wave_prefers_g1_arm_action_preset(self) -> None:
        channel = FakeChannel()
        loco = FakeLocoClient()
        arm = FakeArmActionClient()
        monitor: FakeArmActionMonitor | None = None

        def create_monitor(callback: Callable[[str], None]) -> FakeArmActionMonitor:
            nonlocal monitor
            monitor = FakeArmActionMonitor(callback)

            def publish_action_states(action_id: int) -> None:
                if monitor is None:
                    return
                monitor.emit(
                    f'{{"holding":false,"id":{action_id},"name":"face wave"}}'
                )
                monitor.emit(
                    '{"holding":false,"id":99,"name":"release arm"}'
                )

            arm.on_execute = publish_action_states
            return monitor

        adapter = UnitreeG1Adapter(
            UnitreeG1Config(network_interface="eth0"),
            bindings=UnitreeBindings(
                channel=channel,
                create_loco_client=lambda: loco,
                create_arm_action_client=lambda: arm,
                create_arm_action_monitor=create_monitor,
            ),
        )
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave")
        await adapter.close()

        self.assertTrue(result.success)
        self.assertEqual(result.message, "wave completion verified")
        self.assertEqual(result.verification["action_id"], 25)
        self.assertEqual(arm.action_ids, [25])
        self.assertEqual(loco.wave_flags, [])
        self.assertIsNotNone(monitor)
        if monitor is not None:
            self.assertEqual(monitor.init_count, 1)
            self.assertEqual(monitor.close_count, 1)

    async def test_wave_fails_verification_without_arm_action_monitor(self) -> None:
        channel = FakeChannel()
        loco = FakeLocoClient()
        arm = FakeArmActionClient()
        adapter = UnitreeG1Adapter(
            UnitreeG1Config(network_interface="eth0"),
            bindings=UnitreeBindings(
                channel=channel,
                create_loco_client=lambda: loco,
                create_arm_action_client=lambda: arm,
            ),
        )
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave")
        await adapter.close()

        self.assertEqual(result.status, SkillStatus.VERIFICATION_FAILED)
        self.assertEqual(result.failure_code, FailureCode.VERIFICATION_FAILED)
        self.assertFalse(result.verification["observable"])

    async def test_wave_fails_verification_when_another_action_interrupts(self) -> None:
        channel = FakeChannel()
        loco = FakeLocoClient()
        arm = FakeArmActionClient()

        def create_monitor(callback: Callable[[str], None]) -> FakeArmActionMonitor:
            monitor = FakeArmActionMonitor(callback)

            def publish_interruption(action_id: int) -> None:
                monitor.emit(
                    f'{{"holding":false,"id":{action_id},"name":"face wave"}}'
                )
                monitor.emit(
                    '{"holding":false,"id":23,"name":"right hand up"}'
                )
                monitor.emit(
                    '{"holding":false,"id":99,"name":"release arm"}'
                )

            arm.on_execute = publish_interruption
            return monitor

        adapter = UnitreeG1Adapter(
            bindings=UnitreeBindings(
                channel=channel,
                create_loco_client=lambda: loco,
                create_arm_action_client=lambda: arm,
                create_arm_action_monitor=create_monitor,
            )
        )
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave")
        await adapter.close()

        self.assertEqual(result.status, SkillStatus.VERIFICATION_FAILED)
        self.assertEqual(result.verification["interrupting_action_id"], 23)

    async def test_arm_action_fsm_error_is_explained(self) -> None:
        channel = FakeChannel()
        loco = FakeLocoClient()
        arm = FakeArmActionClient()
        arm.action_status = 7404
        adapter = UnitreeG1Adapter(
            UnitreeG1Config(network_interface="eth0"),
            bindings=UnitreeBindings(
                channel=channel,
                create_loco_client=lambda: loco,
                create_arm_action_client=lambda: arm,
            ),
        )
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave")
        await adapter.close()

        self.assertFalse(result.success)
        self.assertIn("FSM 500, 501, or 801", result.message)

    async def test_disconnected_adapter_fails_wave_precondition(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave")

        self.assertEqual(result.status, SkillStatus.PRECONDITION_FAILED)
        self.assertEqual(client.wave_flags, [])

    async def test_wave_rejects_unsupported_fsm(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        client.fsm_id = 1
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave")
        await adapter.close()

        self.assertFalse(result.success)
        self.assertIn("does not support arm actions", result.message)
        self.assertEqual(client.wave_flags, [])

    async def test_nonzero_wave_status_becomes_robot_error(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        client.wave_status = 42
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())
        await adapter.connect()

        result = await runtime.execute("wave")
        await adapter.close()

        self.assertEqual(result.failure_code, FailureCode.ROBOT_ERROR)
        self.assertIn("SDK status 42", result.message)
        self.assertEqual(client.stop_count, 0)

    async def test_stop_is_an_explicit_sdk_command(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        await adapter.connect()

        await adapter.stop()
        await adapter.close()

        self.assertEqual(client.stop_count, 1)

    async def test_move_velocity_uses_noncontinuous_sdk_failsafe(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        await adapter.connect()

        await adapter.move_velocity(-0.2, 0.0, 0.0)
        await adapter.stop()
        await adapter.close()

        self.assertEqual(client.move_calls, [(-0.2, 0.0, 0.0, False)])
        self.assertEqual(client.stop_count, 1)

    async def test_connect_and_close_are_idempotent(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)

        await adapter.connect()
        await adapter.connect()
        await adapter.close()
        await adapter.close()

        self.assertEqual(channel.initialize_calls, [(7, "eth0")])
        self.assertEqual(channel.release_count, 1)
        self.assertEqual(client.init_count, 1)

    async def test_connect_failure_releases_initialized_channel(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        client.init_error = RuntimeError("client init failed")
        adapter = self.build_adapter(channel, client)

        with self.assertRaisesRegex(RobotCommandError, "client init failed"):
            await adapter.connect()

        self.assertEqual(channel.release_count, 1)
        self.assertFalse(adapter.connected)

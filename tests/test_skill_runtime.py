from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from core.context import SkillContext
from core.models import SkillArgs, SkillMetadata, SkillResult
from core.registry import SkillRegistry
from core.runtime import SkillRuntime
from core.skill import RobotSkill
from core.types import FailureCode, SkillStatus
from robot.base import RobotCommandError, RobotState
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
    ) -> None:
        self.hardware = hardware
        self.connected = connected
        self.wave_error = wave_error
        self.move_error = move_error
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


class SkillRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_wave_runs_through_runtime(self) -> None:
        robot = FakeRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave", arm="right")

        self.assertTrue(result.success)
        self.assertEqual(result.status, SkillStatus.SUCCEEDED)
        self.assertEqual(result.data, {"arm": "right"})
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

    async def test_runtime_wave_uses_sdk_bindings_directly(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        await adapter.connect()
        result = await runtime.execute("wave", arm="right")
        state = await adapter.get_state()
        await adapter.close()

        self.assertTrue(result.success)
        self.assertEqual(channel.initialize_calls, [(7, "eth0")])
        self.assertEqual(channel.release_count, 1)
        self.assertEqual(client.timeout_s, 4.0)
        self.assertEqual(client.init_count, 1)
        self.assertEqual(client.wave_flags, [False])
        self.assertEqual(client.stop_count, 0)
        self.assertEqual(state.details, {"fsm_id": 500})
        self.assertFalse(adapter.connected)

    async def test_disconnected_adapter_fails_wave_precondition(self) -> None:
        channel = FakeChannel()
        client = FakeLocoClient()
        adapter = self.build_adapter(channel, client)
        runtime = SkillRuntime(adapter)
        runtime.register(WaveSkill())

        result = await runtime.execute("wave")

        self.assertEqual(result.status, SkillStatus.PRECONDITION_FAILED)
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

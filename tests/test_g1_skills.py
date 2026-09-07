from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from robot import SimulatedRobotAdapter, UnitreeG1Adapter
from skills import (
    build_g1_all_skills,
    build_g1_autonomy_skills,
    build_g1_operator_skills,
    register_g1_skills,
)
from skills.motions import HandshakeSkill


class G1SkillCatalogTests(unittest.TestCase):
    def test_all_catalog_combines_autonomy_and_operator_skills(self) -> None:
        self.assertEqual(
            len(build_g1_all_skills()),
            len(build_g1_autonomy_skills()) + len(build_g1_operator_skills()),
        )

    def test_autonomy_catalog_contains_every_safe_sdk_action(self) -> None:
        names = {skill.metadata.name for skill in build_g1_autonomy_skills()}
        expected = {
            "wave",
            "wave_hand",
            "handshake",
            "shake_hand",
            "two_hand_kiss",
            "left_kiss",
            "right_kiss",
            "hands_up",
            "clap",
            "high_five",
            "hug",
            "heart",
            "right_heart",
            "reject",
            "right_hand_up",
            "x_ray",
            "high_wave",
            "release_arm",
            "squat",
            "sit",
            "stand_up",
            "high_stand",
            "low_stand",
            "balance_stand",
            "move",
            "move_forward",
            "move_backward",
            "move_left",
            "move_right",
            "turn_left",
            "turn_right",
            "stop",
            "stop_move",
        }
        self.assertEqual(names, expected)

    def test_operator_catalog_is_separate(self) -> None:
        names = {skill.metadata.name for skill in build_g1_operator_skills()}
        self.assertEqual(
            names,
            {
                "start",
                "damp",
                "zero_torque",
                "wave_with_turn",
                "continuous_gait",
                "switch_move_mode",
                "set_speed_mode",
                "set_fsm_id",
                "set_balance_mode",
                "set_swing_height",
                "set_stand_height",
                "set_velocity",
                "move_sdk",
                "set_task_id",
                "switch_to_user_ctrl",
                "switch_to_internal_ctrl",
                "fsm_api",
                "execute_custom_arm_action",
                "stop_custom_arm_action",
            },
        )
        self.assertTrue(
            all("operator_only" in skill.metadata.tags for skill in build_g1_operator_skills())
        )

    def test_register_defaults_keep_dangerous_controls_out_of_registry(self) -> None:
        runtime = __import__("core.runtime", fromlist=["SkillRuntime"]).SkillRuntime(
            SimulatedRobotAdapter()
        )
        register_g1_skills(runtime)
        self.assertFalse(runtime.registry.exists("zero_torque"))
        self.assertTrue(runtime.registry.exists("handshake"))


class G1SkillExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_preset_action_records_sdk_id_in_simulation(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = __import__("core.runtime", fromlist=["SkillRuntime"]).SkillRuntime(robot)
        register_g1_skills(runtime)

        result = await runtime.execute("high_five")

        self.assertTrue(result.success)
        self.assertEqual(
            robot.events,
            [
                (
                    "arm_action",
                    {"action_id": 18, "action_name": "high five"},
                )
            ],
        )

    async def test_handshake_releases_after_bounded_duration(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = __import__("core.runtime", fromlist=["SkillRuntime"]).SkillRuntime(robot)
        runtime.register(HandshakeSkill())

        with patch("skills.motions.arm_actions.asyncio.sleep", new=AsyncMock()):
            result = await runtime.execute("handshake", duration_s=2.0)

        self.assertTrue(result.success)
        self.assertEqual(
            robot.events,
            [
                (
                    "arm_action",
                    {"action_id": 27, "action_name": "shake hand"},
                ),
                ("release_arm", None),
            ],
        )

    async def test_move_and_stop_are_bounded(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = __import__("core.runtime", fromlist=["SkillRuntime"]).SkillRuntime(
            robot
        )
        register_g1_skills(runtime)

        with patch("skills.motions.directional.asyncio.sleep", new=AsyncMock()):
            result = await runtime.execute("move", forward_m_s=0.2, duration_s=0.1)

        self.assertTrue(result.success)
        self.assertEqual(
            robot.events,
            [
                ("move_velocity", (0.2, 0.0, 0.0)),
                ("stop", None),
            ],
        )


class _RecordingLoco:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str):
        def call(*args: object) -> int:
            self.calls.append((name, args))
            return 0

        return call


class _RecordingArm:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute_action(self, action: int | str) -> int:
        self.calls.append(action)
        return 0

    def stop_custom_action(self) -> int:
        self.calls.append("stop_custom_action")
        return 0


class G1SdkMappingTests(unittest.TestCase):
    def test_low_level_loco_skills_map_to_sdk_methods(self) -> None:
        loco = _RecordingLoco()
        adapter = UnitreeG1Adapter()
        adapter._loco = loco
        adapter._channel_ready = True

        adapter._execute_loco_action_sync(
            "set_velocity",
            {"vx": 0.2, "vy": 0.0, "omega": 0.1},
        )
        adapter._execute_loco_action_sync(
            "move_sdk",
            {
                "vx": 0.1,
                "vy": -0.1,
                "vyaw": 0.2,
                "continuous_move": False,
            },
        )
        adapter._execute_loco_action_sync(
            "switch_to_internal_ctrl",
            {"mode": "walkrun"},
        )

        self.assertEqual(loco.calls[0], ("set_velocity", (0.2, 0.0, 0.1, 1.0)))
        self.assertEqual(
            loco.calls[1],
            ("move", (0.1, -0.1, 0.2, False)),
        )
        self.assertEqual(loco.calls[2][0], "switch_to_internal_ctrl")

    def test_custom_arm_action_and_stop_map_to_arm_client(self) -> None:
        arm = _RecordingArm()
        adapter = UnitreeG1Adapter()
        adapter._arm_action = arm
        adapter._channel_ready = True

        adapter._execute_arm_action_sync(18, "high five")
        adapter._execute_arm_action_sync(99, "release arm")
        adapter._execute_custom_arm_action_sync("my_teach_action")
        adapter._stop_custom_arm_action_sync()

        self.assertEqual(arm.calls, [18, 99, "my_teach_action", "stop_custom_action"])

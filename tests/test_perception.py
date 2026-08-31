from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import cast

from core.runtime import SkillRuntime
from core.types import FailureCode
from perception import (
    PerceptionError,
    PerceptionResult,
    PersonGreetingLoop,
    RealSensePersonDetector,
    WorldState,
)
from perception.realsense import RealSenseBindings
from robot import RobotCommandError, RobotState, SimulatedRobotAdapter
from skills.motions import WaveSkill


class FailingRobotAdapter:
    def __init__(self) -> None:
        self.wave_count = 0

    async def get_state(self) -> RobotState:
        return RobotState(hardware=False, connected=True)

    async def stop(self) -> None:
        pass

    async def wave(self, arm: str) -> None:
        self.wave_count += 1
        raise RobotCommandError("wave rejected")


def observation(at_s: float, *, people: int) -> PerceptionResult:
    return PerceptionResult(observed_at_s=at_s, person_count=people)


class PersonGreetingLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_visible_person_is_greeted_only_once(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        loop = PersonGreetingLoop(runtime)

        first = await loop.process(observation(1.0, people=1))
        repeated = await loop.process(observation(1.1, people=1))

        self.assertIsNotNone(first)
        assert first is not None
        self.assertTrue(first.success)
        self.assertIsNone(repeated)
        self.assertEqual(robot.events, [("wave", "right")])

    async def test_brief_missed_detection_does_not_repeat_greeting(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        loop = PersonGreetingLoop(
            runtime,
            WorldState(absence_reset_s=2.0),
        )

        await loop.process(observation(1.0, people=1))
        await loop.process(observation(1.5, people=0))
        result = await loop.process(observation(1.6, people=1))

        self.assertIsNone(result)
        self.assertEqual(robot.events, [("wave", "right")])

    async def test_person_reentry_after_absence_triggers_second_greeting(self) -> None:
        robot = SimulatedRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        loop = PersonGreetingLoop(
            runtime,
            WorldState(absence_reset_s=2.0),
        )

        await loop.process(observation(1.0, people=1))
        await loop.process(observation(3.0, people=0))
        result = await loop.process(observation(3.1, people=1))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.success)
        self.assertEqual(
            robot.events,
            [("wave", "right"), ("wave", "right")],
        )

    async def test_failed_wave_is_retried_after_throttle_interval(self) -> None:
        robot = FailingRobotAdapter()
        runtime = SkillRuntime(robot)
        runtime.register(WaveSkill())
        loop = PersonGreetingLoop(
            runtime,
            WorldState(greeting_retry_s=5.0),
        )

        failed = await loop.process(observation(1.0, people=1))
        throttled = await loop.process(observation(5.9, people=1))
        retried = await loop.process(observation(6.0, people=1))

        self.assertIsNotNone(failed)
        assert failed is not None
        self.assertEqual(failed.failure_code, FailureCode.ROBOT_ERROR)
        self.assertIsNone(throttled)
        self.assertIsNotNone(retried)
        self.assertEqual(robot.wave_count, 2)

    async def test_out_of_order_observation_is_rejected(self) -> None:
        runtime = SkillRuntime(SimulatedRobotAdapter())
        runtime.register(WaveSkill())
        loop = PersonGreetingLoop(runtime)
        await loop.process(observation(2.0, people=0))

        with self.assertRaisesRegex(ValueError, "time ordered"):
            await loop.process(observation(1.0, people=0))


class FakeColorFrame:
    def get_data(self) -> object:
        return [[0]]

    def get_width(self) -> int:
        return 640

    def get_height(self) -> int:
        return 480


class FakeDepthFrame(FakeColorFrame):
    def __init__(self, distances: dict[tuple[int, int], float]) -> None:
        self.distances = distances
        self.queries: list[tuple[int, int]] = []

    def get_distance(self, x: int, y: int) -> float:
        self.queries.append((x, y))
        return self.distances[(x, y)]


class FakeFrames:
    def __init__(self, depth: FakeDepthFrame) -> None:
        self.color = FakeColorFrame()
        self.depth = depth

    def get_color_frame(self) -> FakeColorFrame:
        return self.color

    def get_depth_frame(self) -> FakeDepthFrame:
        return self.depth


class FakePipeline:
    def __init__(self, frames: FakeFrames) -> None:
        self.frames = frames
        self.started_with: object | None = None
        self.timeout_calls: list[int] = []
        self.stop_count = 0

    def start(self, config: object) -> object:
        self.started_with = config
        return object()

    def wait_for_frames(self, timeout_ms: int) -> FakeFrames:
        self.timeout_calls.append(timeout_ms)
        return self.frames

    def stop(self) -> None:
        self.stop_count += 1


class FakeConfig:
    def __init__(self) -> None:
        self.serials: list[str] = []
        self.streams: list[tuple[object, ...]] = []

    def enable_device(self, serial: str) -> None:
        self.serials.append(serial)

    def enable_stream(self, *args: object) -> None:
        self.streams.append(args)


class FakeAlign:
    def __init__(self) -> None:
        self.inputs: list[FakeFrames] = []

    def process(self, frames: FakeFrames) -> FakeFrames:
        self.inputs.append(frames)
        return frames


class FakeHog:
    def __init__(
        self,
        rectangles: list[tuple[int, int, int, int]],
        scores: list[float],
    ) -> None:
        self.rectangles = rectangles
        self.scores = scores
        self.detector: object | None = None

    def setSVMDetector(self, detector: object) -> None:
        self.detector = detector

    def detectMultiScale(
        self,
        image: object,
        *,
        winStride: tuple[int, int],
        padding: tuple[int, int],
        scale: float,
    ) -> tuple[list[tuple[int, int, int, int]], list[float]]:
        return self.rectangles, self.scores


class FakeNumpy:
    def asanyarray(self, value: object) -> object:
        return value


def make_bindings(
    *,
    pipeline: FakePipeline,
    config: FakeConfig,
    align: FakeAlign,
    hog: FakeHog,
) -> RealSenseBindings:
    realsense = SimpleNamespace(
        pipeline=lambda: pipeline,
        config=lambda: config,
        align=lambda stream: align,
        stream=SimpleNamespace(depth="depth", color="color"),
        format=SimpleNamespace(z16="z16", bgr8="bgr8"),
    )
    opencv = SimpleNamespace(
        HOGDescriptor=lambda: hog,
        HOGDescriptor_getDefaultPeopleDetector=lambda: "detector",
    )
    namespace = SimpleNamespace(
        realsense=realsense,
        numpy=FakeNumpy(),
        opencv=opencv,
    )
    return cast(RealSenseBindings, namespace)


class RealSensePersonDetectorTests(unittest.TestCase):
    def test_capture_aligns_depth_and_filters_distant_people(self) -> None:
        depth = FakeDepthFrame({(30, 50): 1.5, (120, 130): 6.0})
        frames = FakeFrames(depth)
        pipeline = FakePipeline(frames)
        config = FakeConfig()
        align = FakeAlign()
        hog = FakeHog(
            [(10, 20, 40, 60), (100, 100, 40, 60)],
            [1.0, 2.0],
        )
        detector = RealSensePersonDetector(
            serial="camera-1",
            frame_timeout_ms=1234,
            min_score=0.5,
            max_distance_m=4.0,
            bindings=make_bindings(
                pipeline=pipeline,
                config=config,
                align=align,
                hog=hog,
            ),
        )

        detector.open()
        result = detector.capture()
        detector.close()

        self.assertEqual(config.serials, ["camera-1"])
        self.assertEqual(
            config.streams,
            [
                ("depth", 640, 480, "z16", 30),
                ("color", 640, 480, "bgr8", 30),
            ],
        )
        self.assertEqual(pipeline.timeout_calls, [1234])
        self.assertEqual(align.inputs, [frames])
        self.assertEqual(depth.queries, [(30, 50), (120, 130)])
        self.assertEqual(result.person_count, 1)
        self.assertEqual(result.nearest_person_distance_m, 1.5)
        self.assertEqual(result.source, "realsense:camera-1")
        self.assertIsNotNone(result.confidence)
        self.assertEqual(pipeline.stop_count, 1)

    def test_capture_requires_open_camera(self) -> None:
        detector = RealSensePersonDetector(bindings=cast(RealSenseBindings, object()))

        with self.assertRaisesRegex(PerceptionError, "not open"):
            detector.capture()

    def test_close_is_idempotent(self) -> None:
        depth = FakeDepthFrame({})
        pipeline = FakePipeline(FakeFrames(depth))
        detector = RealSensePersonDetector(
            bindings=make_bindings(
                pipeline=pipeline,
                config=FakeConfig(),
                align=FakeAlign(),
                hog=FakeHog([], []),
            )
        )

        detector.open()
        detector.close()
        detector.close()

        self.assertEqual(pipeline.stop_count, 1)

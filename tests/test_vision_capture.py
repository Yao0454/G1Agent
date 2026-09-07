import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path

from agent.vision_capture import VisionCapture
from agent import VisionDecisionAgent, VisionPolicyWorker
from core.runtime import SkillRuntime
from perception import VideoBuffer
from robot import SimulatedRobotAdapter
from tests.test_vision_policy import camera_frame, FakeVisionInvoker


class CaptureTests(unittest.TestCase):
    def test_preserves_bytes_timestamps_and_limit_without_deleting(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = VisionCapture(Path(directory), limit=1)
            folder = capture.begin([camera_frame(1), camera_frame(2)])
            self.assertEqual((folder / "frame-00.jpg").read_bytes(), b"jpeg")
            metadata = json.loads((folder / "input.json").read_text())
            self.assertEqual([f["observed_at_s"] for f in metadata["frames"]], [1, 2])
            capture.finish(folder, {"decision": {"action": "ignore"}})
            self.assertFalse(capture.available)
            self.assertIsNone(capture.begin([camera_frame(3)]))
            self.assertTrue((folder / "result.json").exists())
            other = VisionCapture(Path(directory), limit=1)
            self.assertNotEqual(folder, other.begin([camera_frame(4)]))

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            VisionCapture(Path("unused"), 0)


class CaptureWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_and_error_are_linked_to_saved_inputs(self):
        for output in ({"action": "ignore", "reason": "test"}, "bad JSON"):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                buffer = VideoBuffer(window_s=2, max_frames=10)
                buffer.push(camera_frame(time.monotonic()))
                invoker = FakeVisionInvoker([output])
                worker = VisionPolicyWorker(
                    SkillRuntime(SimulatedRobotAdapter()),
                    VisionDecisionAgent(invoker=invoker), buffer,
                    interval_s=0.01, capture=VisionCapture(Path(directory), 1),
                )
                await worker.start()
                try:
                    for _ in range(100):
                        results = list(Path(directory).glob("*/window-*/result.json"))
                        if results:
                            break
                        await asyncio.sleep(0.01)
                    self.assertEqual(len(results), 1)
                    result = json.loads(results[0].read_text())
                    self.assertIn("decision" if isinstance(output, dict) else "error", result)
                    self.assertEqual(invoker.calls[0][0][0], (results[0].parent / "frame-00.jpg").read_bytes())
                finally:
                    await worker.stop()

import io
import unittest
from dataclasses import replace

from PIL import Image
from agent import VisionPolicyWorker, VisionDecisionAgent
from core.runtime import SkillRuntime
from perception import VideoBuffer
from robot import SimulatedRobotAdapter
from tests.test_vision_policy import camera_frame, FakeVisionInvoker


class RotationTests(unittest.TestCase):
    def worker(self, degrees):
        return VisionPolicyWorker(
            SkillRuntime(SimulatedRobotAdapter()),
            VisionDecisionAgent(invoker=FakeVisionInvoker([])),
            VideoBuffer(), rotation_deg=degrees,
        )

    def test_orientation_preserves_depth_timestamp_and_source(self):
        image = Image.new("RGB", (80, 40), "red")
        image.paste("blue", (40, 0, 80, 40))
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        original = replace(camera_frame(10), rgb=encoded.getvalue(), depth=object())
        for degrees in (90, 180, 270):
            with self.subTest(degrees=degrees):
                rotated = self.worker(degrees)._orient_frames((original,))[0]
                decoded = Image.open(io.BytesIO(rotated.rgb))
                self.assertEqual(decoded.size, (80, 40) if degrees == 180 else (40, 80))
                self.assertIs(rotated.depth, original.depth)
                self.assertIs(rotated.observation, original.observation)
                self.assertEqual(rotated.observed_at_s, 10)
                self.assertEqual(rotated.nearest_obstacle_distance_m, original.nearest_obstacle_distance_m)
                if degrees == 180:
                    self.assertGreater(decoded.getpixel((10, 20))[2], 240)
        self.assertEqual(original.rgb, encoded.getvalue())

    def test_zero_is_identity_and_invalid_rotation_rejected(self):
        frames = (camera_frame(1),)
        self.assertIs(self.worker(0)._orient_frames(frames), frames)
        with self.assertRaises(ValueError):
            self.worker(45)

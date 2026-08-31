from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from perception.realsense_bridge import RealSenseBridge

FAKE_WORKER = """
import json
import sys

print(json.dumps({"type": "ready"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if request.get("command") == "capture":
        print(json.dumps({
            "type": "observation",
            "result": {
                "observed_at_s": 12.5,
                "person_count": 1,
                "nearest_person_distance_m": 1.25,
                "confidence": 0.9,
                "source": "realsense:test",
            },
        }), flush=True)
    elif request.get("command") == "close":
        print(json.dumps({"type": "closed"}), flush=True)
        break
"""


class RealSenseBridgeTests(unittest.TestCase):
    def test_persistent_worker_returns_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory, "fake_worker.py")
            worker.write_text(FAKE_WORKER, encoding="utf-8")
            bridge = RealSenseBridge(
                serial=None,
                width=640,
                height=480,
                fps=30,
                frame_timeout_ms=1000,
                min_score=0.5,
                max_distance_m=4.0,
                python_executable=sys.executable,
                worker_path=worker,
            )

            bridge.open()
            first = bridge.capture()
            second = bridge.capture()
            bridge.close()

        self.assertEqual(first.person_count, 1)
        self.assertEqual(first.nearest_person_distance_m, 1.25)
        self.assertEqual(first.source, "realsense:test")
        self.assertEqual(second, first)
        self.assertFalse(bridge.opened)


if __name__ == "__main__":
    unittest.main()

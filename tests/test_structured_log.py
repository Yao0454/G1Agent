from __future__ import annotations

import io
import json
import unittest

from app.structured_log import LOG_SCHEMA, emit_log


class StructuredLogTests(unittest.TestCase):
    def test_log_envelope_always_includes_owner_and_fixed_keys(self) -> None:
        stream = io.StringIO()

        emit_log(
            owner="agent.vision_policy",
            event_type="vision_decision",
            data={"action": "continue"},
            stream=stream,
        )

        payload = json.loads(stream.getvalue())
        self.assertEqual(
            list(payload),
            ["schema", "timestamp", "level", "type", "owner", "data"],
        )
        self.assertEqual(payload["schema"], LOG_SCHEMA)
        self.assertEqual(payload["owner"], "agent.vision_policy")
        self.assertEqual(payload["data"], {"action": "continue"})


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import AsyncMock

from agent.decision import DecisionAgentError
from agent.vision_policy import OllamaVisionInvoker


class OllamaVisionTests(unittest.IsolatedAsyncioTestCase):
    def invoker(self, payload):
        invoker = OllamaVisionInvoker("test", constrain_json=False)
        invoker._client = AsyncMock()
        invoker._client.chat.return_value = payload
        return invoker

    async def test_generic_json_is_explicit_nonstreaming(self):
        invoker = self.invoker({
            "done": True, "done_reason": "stop", "message": {"content": "{}"},
        })
        self.assertEqual(await invoker.ainvoke([b"jpeg"], "test"), "{}")
        kwargs = invoker._client.chat.call_args.kwargs
        self.assertEqual(kwargs["format"], "json")
        self.assertIs(kwargs["stream"], False)
        self.assertNotIn("think", kwargs)

    async def test_thinking_can_be_explicitly_disabled(self):
        invoker = self.invoker({"done": True, "message": {"content": "{}"}})
        invoker.think = False
        await invoker.ainvoke([b"jpeg"], "test")
        self.assertIs(invoker._client.chat.call_args.kwargs["think"], False)

    async def test_incomplete_and_token_limited_responses_rejected(self):
        for payload in (
            {"done": False}, {},
            {"done": True, "done_reason": "length", "message": {"content": "{}"}},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(DecisionAgentError):
                    await self.invoker(payload).ainvoke([b"jpeg"], "test")

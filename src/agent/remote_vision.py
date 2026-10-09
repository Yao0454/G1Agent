"""Client for the UnifoLM vision server's persistent inference endpoint."""

import base64
import time
from collections.abc import Sequence

import httpx

from .decision import DecisionAgentError
from .vision_policy import OllamaVisionInvoker

REMOTE_VISION_URL = "http://192.168.31.143:8011"
REMOTE_VISION_MODEL = "models/UnifoLM-ER-1"


class RemoteVisionInvoker:
    # Keep the 256-token remote response focused on the next action.
    response_protocol = "decision"

    def __init__(
        self,
        model_name: str = REMOTE_VISION_MODEL,
        *,
        base_url: str = REMOTE_VISION_URL,
        max_new_tokens: int = 256,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not 1 <= max_new_tokens <= 256:
            raise ValueError("remote vision token budget must be between 1 and 256")
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.last_metrics: dict[str, object] = {}
        self._request_id = 0
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=120,
            trust_env=False,
            transport=transport,
        )

    async def warmup(self) -> None:
        response = await self._client.get("/health")
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ready":
            raise DecisionAgentError("remote vision server is not ready")
        if payload.get("model") != self.model_name:
            raise DecisionAgentError(
                "remote vision server model does not match configuration"
            )

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        if not 1 <= len(frames) <= 8:
            raise ValueError("remote vision requires between 1 and 8 frames")
        if not prompt.strip() or len(prompt) > 32000:
            raise ValueError("remote vision prompt must contain 1 to 32000 characters")
        self._request_id += 1
        request_id = self._request_id
        started = time.monotonic()
        self.last_metrics = {}
        response = await self._client.post(
            "/v1/vision/invoke",
            json={
                "request_id": request_id,
                "model": self.model_name,
                "frames": [
                    base64.b64encode(OllamaVisionInvoker._as_bytes(frame)).decode(
                        "ascii"
                    )
                    for frame in frames
                ],
                "prompt": prompt,
                "max_new_tokens": self.max_new_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("request_id") != request_id:
            raise DecisionAgentError("remote vision returned a mismatched request ID")
        output = payload.get("output")
        if not isinstance(output, str) or not output.strip():
            raise DecisionAgentError("remote vision returned no model output")
        metrics = payload.get("metrics", {})
        if not isinstance(metrics, dict):
            raise DecisionAgentError("remote vision returned invalid metrics")
        generated = metrics.get("generated_tokens")
        if isinstance(generated, (int, float)) and generated >= self.max_new_tokens:
            raise DecisionAgentError("remote vision exhausted the output token budget")
        elapsed = time.monotonic() - started
        self.last_metrics = {
            **metrics,
            "remote_request_id": request_id,
            "round_trip_s": round(elapsed, 3),
            "frame_count": len(frames),
        }
        server_total = metrics.get("server_total_s")
        if isinstance(server_total, (int, float)):
            self.last_metrics["network_rtt_s"] = round(
                max(0, elapsed - server_total), 3
            )
        return output

    async def close(self) -> None:
        await self._client.aclose()

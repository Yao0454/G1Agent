"""Small Ollama-backed conversation brain for the robot demo."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .async_utils import run_blocking

SUPPORTED_ACTIONS = (
    "none",
    "wave",
    "shake_hand",
    "nod",
    "shake_head",
    "stand",
    "sit",
    "move_forward",
    "turn_left",
    "turn_right",
    "dance",
    "stop",
)

SYSTEM_PROMPT = """你是一个机器人助手。

你需要和用户自然对话，并根据用户的话选择一个机器人动作。

允许的 action 只有：none, wave, shake_hand, nod, shake_head, stand, sit,
move_forward, turn_left, turn_right, dance, stop。

规则：
1. 用户没有要求动作时使用 none。
2. action 必须严格从允许列表中选择，不能创造新动作。
3. speech 是你准备对用户说的话，简短、自然，不要描述 JSON。
4. 只输出 JSON 对象，不要 Markdown，不要额外解释。
5. JSON 格式必须是：{"speech": "...", "action": "..."}。
"""


@dataclass(frozen=True, slots=True)
class RobotResponse:
    speech: str
    action: str = "none"
    used_fallback: bool = False

    def __getitem__(self, key: str) -> str:
        if key == "speech":
            return self.speech
        if key == "action":
            return self.action
        raise KeyError(key)

    def to_dict(self) -> dict[str, str]:
        return {"speech": self.speech, "action": self.action}


class OllamaBrain:
    """Call Ollama's local ``/api/chat`` endpoint with a tiny JSON contract.

    If Ollama is not running, a deterministic keyword fallback keeps the demo
    usable for rehearsals and makes failures visible without crashing the loop.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        configured_url = (
            base_url
            or os.getenv("OLLAMA_URL")
            or os.getenv("OLLAMA_HOST")
            or "http://127.0.0.1:11434"
        )
        self.url = self._chat_url(configured_url)
        self.timeout = timeout
        # Ollama normally runs on loopback; do not let a corporate HTTP proxy
        # turn a local connection failure into a long, opaque timeout.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @staticmethod
    def _chat_url(value: str) -> str:
        if "://" not in value:
            value = f"http://{value}"
        value = value.rstrip("/")
        return value if value.endswith("/api/chat") else f"{value}/api/chat"

    async def chat(self, text: str) -> RobotResponse:
        return await run_blocking(self._chat_sync, text)

    def _chat_sync(self, text: str) -> RobotResponse:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "options": {"temperature": 0.2},
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            if not isinstance(body, dict):
                raise TypeError("Ollama response must be a JSON object")
            message = body.get("message", {})
            if not isinstance(message, dict):
                raise TypeError("Ollama response message must be an object")
            content = message.get("content", "")
            return self._apply_explicit_overrides(text, self._parse_response(content))
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace").strip()
            except OSError:
                detail = ""
            suffix = f": {detail[:240]}" if detail else ""
            print(f"[brain] Ollama HTTP {exc.code}{suffix}; using local fallback.")
            return self._fallback(text)
        except (
            OSError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            print(f"[brain] Ollama unavailable ({exc}); using local fallback.")
            return self._fallback(text)

    @classmethod
    def _parse_response(cls, content: Any) -> RobotResponse:
        if isinstance(content, dict):
            data = content
        else:
            raw = str(content).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
                if match is None:
                    raise ValueError("Ollama response did not contain a JSON object")
                data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise TypeError("Ollama response JSON must be an object")

        speech = str(data.get("speech", "")).strip()
        action = str(data.get("action", "none")).strip().lower()
        if action not in SUPPORTED_ACTIONS:
            action = "none"
        if not speech:
            speech = "好的。" if action == "none" else "好的，我来做。"
        return RobotResponse(speech=speech, action=action)

    @classmethod
    def _fallback(cls, text: str) -> RobotResponse:
        normalized = text.lower()
        keyword_actions = (
            (("握手", "shake hand", "handshake"), "shake_hand", "好的，我来和你握手！"),
            (
                ("挥手", "招手", "打个招呼", "wave", "hello"),
                "wave",
                "大家好，很高兴见到大家！",
            ),
            (("点头", "同意", "nod"), "nod", "好的，我同意。"),
            (("摇头", "不同意", "shake"), "shake_head", "这个我不建议。"),
            (("站起来", "站立", "起立", "stand"), "stand", "好的，我站起来。"),
            (("坐下", "坐下去", "sit"), "sit", "好的，我坐下。"),
            (
                ("向前", "前进", "往前", "move", "forward"),
                "move_forward",
                "没问题，向前一点。",
            ),
            (("左转", "向左", "turn left"), "turn_left", "好的，向左转。"),
            (("右转", "向右", "turn right"), "turn_right", "好的，向右转。"),
            (("跳舞", "舞蹈", "dance"), "dance", "那我来跳一段。"),
            (("停止", "停下", "stop"), "stop", "好的，停止动作。"),
        )
        for keywords, action, speech in keyword_actions:
            if any(keyword in normalized for keyword in keywords):
                return RobotResponse(speech=speech, action=action, used_fallback=True)
        return RobotResponse(
            speech="你好！今天有什么想让我做的吗？", used_fallback=True
        )

    @staticmethod
    def _apply_explicit_overrides(text: str, response: RobotResponse) -> RobotResponse:
        # Keep high-confidence, explicit Chinese commands stable even when a
        # small local model picks a nearby exhibition action.
        if "握手" in text and response.action != "shake_hand":
            return RobotResponse(
                speech=response.speech or "好的，我来和你握手！",
                action="shake_hand",
                used_fallback=response.used_fallback,
            )
        return response

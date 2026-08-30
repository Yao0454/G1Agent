"""Small system TTS adapter with a print-only fallback."""

from __future__ import annotations

import shutil
import subprocess

from .async_utils import run_blocking


class SystemTTS:
    def __init__(self, enabled: bool = True, voice: str | None = None) -> None:
        self.enabled = enabled
        self.voice = voice
        self.command = self._find_command()
        self._warned = False

    @staticmethod
    def _find_command() -> str | None:
        for name in ("espeak-ng", "espeak", "say"):
            command = shutil.which(name)
            if command:
                return command
        return None

    async def speak(self, text: str) -> None:
        if not text or not self.enabled:
            return
        await run_blocking(self._speak_sync, text)

    def _speak_sync(self, text: str) -> None:
        if not self.command:
            if not self._warned:
                print("[tts] 未找到 espeak-ng/espeak/say，改为只显示文本。")
                self._warned = True
            return
        command = [self.command]
        if self.voice and self.command.endswith(("espeak", "espeak-ng")):
            command.extend(["-v", self.voice])
        command.append(text)
        try:
            subprocess.run(command, check=True, timeout=max(10, len(text) // 3))
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[tts] 播放失败：{exc}")

"""Microphone input through a system recorder and a local Whisper CLI."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class ASRError(RuntimeError):
    """Raised when local audio recording or transcription is unavailable."""


class MicrophoneASR:
    def __init__(
        self,
        record_seconds: float = 5.0,
        whisper_bin: str | None = None,
        model: str | None = None,
        language: str | None = None,
        audio_device: str | None = None,
    ) -> None:
        self.record_seconds = max(0.5, record_seconds)
        self.whisper_bin = whisper_bin or self._find_whisper()
        self.model = model
        self.language = language
        self.audio_device = audio_device

    @staticmethod
    def _find_whisper() -> str | None:
        for name in ("whisper-cli", "whisper", "whisper-cpp"):
            command = shutil.which(name)
            if command:
                return command
        return None

    def transcribe_once(self) -> str:
        if not self.whisper_bin:
            raise ASRError(
                "找不到 whisper 命令，请安装 Whisper 或改用 --input text。"
            )
        if self._uses_cpp() and not self.model:
            raise ASRError("whisper.cpp 需要 --whisper-model 指向 ggml 模型文件。")
        recorder = shutil.which("arecord") or shutil.which("ffmpeg")
        if not recorder:
            raise ASRError("找不到 arecord 或 ffmpeg，无法录音。")

        with tempfile.TemporaryDirectory(prefix="g1-asr-") as temp_dir:
            wav_path = Path(temp_dir) / "input.wav"
            self._record(recorder, wav_path)
            return self._transcribe(wav_path, Path(temp_dir)).strip()

    def _record(self, recorder: str, wav_path: Path) -> None:
        if Path(recorder).name == "arecord":
            command = [
                recorder,
                "-q",
                "-f",
                "S16_LE",
                "-r",
                "16000",
                "-c",
                "1",
                "-d",
                str(max(1, round(self.record_seconds))),
                str(wav_path),
            ]
            if self.audio_device:
                command[1:1] = ["-D", self.audio_device]
        else:
            command = [
                recorder,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "alsa",
                "-i",
                self.audio_device or "default",
                "-t",
                str(self.record_seconds),
                str(wav_path),
            ]
        try:
            subprocess.run(command, check=True, timeout=self.record_seconds + 10)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ASRError(f"录音失败：{exc}") from exc

    def _transcribe(self, wav_path: Path, output_dir: Path) -> str:
        if self._uses_cpp():
            return self._transcribe_cpp(wav_path, output_dir)

        command = [
            self.whisper_bin or "whisper",
            str(wav_path),
            "--output_dir",
            str(output_dir),
            "--output_format",
            "txt",
            "--fp16",
            "False",
        ]
        if self.model:
            command.extend(["--model", self.model])
        if self.language:
            command.extend(["--language", self.language])
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=max(60.0, self.record_seconds * 20),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ASRError(f"Whisper 转写失败：{exc}") from exc

        text_path = output_dir / f"{wav_path.stem}.txt"
        if text_path.exists():
            return text_path.read_text(encoding="utf-8")
        return result.stdout.strip()

    def _transcribe_cpp(self, wav_path: Path, output_dir: Path) -> str:
        if not self.model:
            raise ASRError("whisper.cpp 需要 --whisper-model 指向 ggml 模型文件。")
        output_base = output_dir / "transcript"
        command = [
            self.whisper_bin or "whisper-cli",
            "-m",
            self.model,
            "-f",
            str(wav_path),
            "-otxt",
            "-of",
            str(output_base),
        ]
        if self.language:
            command.extend(["-l", self.language])
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=max(60.0, self.record_seconds * 20),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ASRError(f"whisper.cpp 转写失败：{exc}") from exc

        text_path = output_base.with_suffix(".txt")
        if text_path.exists():
            return text_path.read_text(encoding="utf-8")
        return result.stdout.strip()

    def _uses_cpp(self) -> bool:
        return Path(self.whisper_bin or "").name in {"whisper-cli", "whisper-cpp"}

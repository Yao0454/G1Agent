"""Voice -> Ollama -> speech + Unitree action demo."""

from __future__ import annotations

import argparse
import asyncio
import os

from .asr import ASRError, MicrophoneASR
from .async_utils import run_blocking
from .brain import OllamaBrain
from .robot import Robot
from .tts import SystemTTS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        choices=("text", "microphone"),
        default=os.getenv("G1_INPUT_MODE", "text"),
        help="text is dependency-free rehearsal; microphone uses arecord/ffmpeg + whisper",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model (default: OLLAMA_MODEL or qwen2.5:3b)",
    )
    parser.add_argument("--ollama-url", default=None, help="Ollama base URL")
    parser.add_argument(
        "--network", default="", help="Unitree DDS interface, e.g. eth0"
    )
    parser.add_argument(
        "--hardware", action="store_true", help="send actions to a physical G1"
    )
    parser.add_argument(
        "--yes", action="store_true", help="skip the physical robot confirmation"
    )
    parser.add_argument(
        "--record-seconds", type=float, default=5.0, help="microphone clip length"
    )
    parser.add_argument(
        "--whisper-bin", default=None, help="path/name of the local whisper command"
    )
    parser.add_argument("--whisper-model", default=None, help="Whisper model name")
    parser.add_argument("--language", default=None, help="Whisper language, e.g. zh")
    parser.add_argument(
        "--audio-device",
        default=os.getenv("G1_AUDIO_DEVICE"),
        help="ALSA capture device for arecord, e.g. hw:2,0",
    )
    parser.add_argument(
        "--tts-voice",
        default=os.getenv("G1_TTS_VOICE"),
        help="espeak voice name, e.g. cmn or zh",
    )
    parser.add_argument("--no-tts", action="store_true", help="disable system TTS")
    parser.add_argument(
        "--once", action="store_true", help="process one utterance and exit"
    )
    return parser.parse_args()


async def _read_text() -> str:
    try:
        return (await run_blocking(input, "你: ")).strip()
    except EOFError:
        return ""


async def _run_turn(
    text: str, brain: OllamaBrain, tts: SystemTTS, robot: Robot
) -> None:
    response = await brain.chat(text)
    print(f"机器人: {response.speech}  [action={response.action}]")
    result = await asyncio.gather(
        tts.speak(response.speech), robot.execute(response.action)
    )
    action_result = result[1]
    if not action_result.ok:
        print(
            f"[robot] action skipped/failed: {action_result.detail or action_result.status}"
        )


async def run(args: argparse.Namespace) -> None:
    brain = OllamaBrain(model=args.model, base_url=args.ollama_url)
    tts = SystemTTS(enabled=not args.no_tts, voice=args.tts_voice)
    robot = Robot(hardware=args.hardware, network=args.network)

    if args.hardware and not args.yes:
        confirmation = await run_blocking(
            input, '即将控制真实 G1，确认周围安全后输入 "G1"： '
        )
        if confirmation.strip() != "G1":
            print("已取消真机模式。")
            return
    if args.hardware:
        robot.connect()

    microphone = None
    if args.input == "microphone":
        microphone = MicrophoneASR(
            record_seconds=args.record_seconds,
            whisper_bin=args.whisper_bin,
            model=args.whisper_model,
            language=args.language,
            audio_device=args.audio_device,
        )
        print("麦克风模式：每次录音固定时长，按 Ctrl-C 退出。")
    else:
        print("文本模式：直接输入中文指令，输入 quit/exit 退出。")

    try:
        while True:
            if microphone is not None:
                print("请说话...")
                try:
                    text = await run_blocking(microphone.transcribe_once)
                except ASRError as exc:
                    print(f"[asr] {exc}")
                    break
                print(f"用户: {text}")
            else:
                text = await _read_text()
            if not text:
                if args.once:
                    break
                continue
            if text.lower() in {"quit", "exit", "q", "退出"}:
                break
            await _run_turn(text, brain, tts, robot)
            if args.once:
                break
    except KeyboardInterrupt:
        print("\n已退出。")
    finally:
        robot.close()


def main() -> int:
    try:
        asyncio.run(run(parse_args()))
    except RuntimeError as exc:
        print(f"错误: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

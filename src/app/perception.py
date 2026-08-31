"""Run the D435i event-to-Agent-to-skill autonomous decision loop."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from adapters import AudioOutputError, UnitreeAudioOutput
from agent import (
    AutonomousDecisionLoop,
    DecisionAgentError,
    DecisionOutcome,
    EventDecisionAgent,
)
from core.runtime import SkillRuntime
from perception import (
    EventDetector,
    PerceptionError,
    PerceptionResult,
    RealSensePersonDetector,
    WorldState,
)
from robot import (
    RobotAdapter,
    RobotCommandError,
    SimulatedRobotAdapter,
    UnitreeG1Adapter,
    UnitreeG1Config,
)
from skills.motions import MoveBackwardSkill, WaveSkill


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="connect to a physical G1 instead of the simulated adapter",
    )
    parser.add_argument(
        "--network",
        default="",
        help="Unitree DDS interface, e.g. eth0",
    )
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen3:1.7b"))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_HOST"))
    parser.add_argument(
        "--decision-timeout-s",
        type=float,
        default=8.0,
        help="maximum time to wait for one Ollama event decision",
    )
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--speaker-id", type=int, default=0)
    parser.add_argument("--camera-serial", help="D435i serial number")
    parser.add_argument(
        "--camera-python",
        help="Python with working pyrealsense2 bindings (default: /usr/bin/python3)",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--frame-timeout-ms", type=int, default=5000)
    parser.add_argument("--min-score", type=float, default=0.5)
    parser.add_argument(
        "--max-distance-m",
        type=float,
        default=4.0,
        help="ignore people with a valid depth beyond this distance",
    )
    parser.add_argument("--absence-reset-s", type=float, default=2.0)
    parser.add_argument("--too-close-m", type=float, default=0.8)
    parser.add_argument("--too-close-release-m", type=float, default=1.0)
    parser.add_argument(
        "--once",
        action="store_true",
        help="capture one frame and exit",
    )
    return parser.parse_args()


def _print_observation(observation: PerceptionResult) -> None:
    print(
        json.dumps(
            {"type": "observation", **observation.to_dict()},
            ensure_ascii=False,
        ),
        flush=True,
    )


def _print_outcome(outcome: DecisionOutcome) -> None:
    print(
        json.dumps(
            {"type": "decision_outcome", **outcome.to_dict()},
            ensure_ascii=False,
        ),
        flush=True,
    )


async def run_perception_loop(
    *,
    camera: RealSensePersonDetector,
    decision_loop: AutonomousDecisionLoop,
    once: bool = False,
    once_wait_s: float = 8.0,
) -> int:
    await decision_loop.start_workers()
    try:
        observation = await asyncio.to_thread(camera.capture)
        _print_observation(observation)
        events = await decision_loop.observe(observation)
        if once:
            if events:
                try:
                    failed = False
                    async with asyncio.timeout(once_wait_s):
                        for _ in events:
                            outcome = await decision_loop.next_outcome()
                            _print_outcome(outcome)
                            failed = failed or (
                                outcome.skill_result is not None
                                and not outcome.skill_result.success
                            )
                    return int(failed)
                except TimeoutError:
                    for error in decision_loop.drain_errors():
                        print(
                            json.dumps(
                                {"type": "decision_error", "message": error},
                                ensure_ascii=False,
                            ),
                            file=sys.stderr,
                            flush=True,
                        )
                    return 1
            return 0

        while True:
            for error in decision_loop.drain_errors():
                print(
                    json.dumps(
                        {"type": "decision_error", "message": error},
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                    flush=True,
                )
            for outcome in decision_loop.drain_outcomes():
                _print_outcome(outcome)
            observation = await asyncio.to_thread(camera.capture)
            _print_observation(observation)
            await decision_loop.observe(observation)
    finally:
        await decision_loop.stop_workers()


async def _run(args: argparse.Namespace) -> int:
    hardware_robot: UnitreeG1Adapter | None = None
    audio: UnitreeAudioOutput | None = None
    robot: RobotAdapter
    if args.hardware:
        hardware_robot = UnitreeG1Adapter(
            UnitreeG1Config(
                network_interface=args.network,
                domain_id=args.domain_id,
            )
        )
        robot = hardware_robot
    else:
        robot = SimulatedRobotAdapter()

    runtime = SkillRuntime(robot)
    runtime.register(WaveSkill())
    runtime.register(MoveBackwardSkill())
    decision_agent = EventDecisionAgent(
        model_name=args.model,
        base_url=args.ollama_url,
        timeout_s=args.decision_timeout_s,
        skill_catalog=runtime.registry.list(),
    )
    camera = RealSensePersonDetector(
        serial=args.camera_serial,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_timeout_ms=args.frame_timeout_ms,
        min_score=args.min_score,
        max_distance_m=args.max_distance_m,
        bridge_python=args.camera_python,
    )
    world_state = WorldState(
        absence_reset_s=args.absence_reset_s,
    )
    event_detector = EventDetector(
        too_close_distance_m=args.too_close_m,
        too_close_release_m=args.too_close_release_m,
    )

    try:
        if hardware_robot is not None:
            await hardware_robot.connect()
            if not args.no_audio:
                audio = UnitreeAudioOutput(
                    hardware_robot,
                    speaker_id=args.speaker_id,
                )
                await audio.connect()
        await asyncio.to_thread(camera.open)
        decision_loop = AutonomousDecisionLoop(
            runtime,
            decision_agent,
            world_state=world_state,
            event_detector=event_detector,
            speech=audio,
        )
        return await run_perception_loop(
            camera=camera,
            decision_loop=decision_loop,
            once=args.once,
            once_wait_s=args.decision_timeout_s + 1.0,
        )
    finally:
        try:
            await asyncio.to_thread(camera.close)
        finally:
            try:
                if audio is not None:
                    await audio.close()
            finally:
                if hardware_robot is not None:
                    await hardware_robot.close()


def main() -> int:
    try:
        return asyncio.run(_run(parse_args()))
    except KeyboardInterrupt:
        return 130
    except (
        AudioOutputError,
        DecisionAgentError,
        PerceptionError,
        RobotCommandError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"type": "error", "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

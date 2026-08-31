"""Run the D435i person-detection to wave-skill loop without an Agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from core.models import SkillResult
from core.runtime import SkillRuntime
from perception import (
    PerceptionError,
    PerceptionResult,
    PersonGreetingLoop,
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
from skills.motions import WaveSkill


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
    parser.add_argument("--camera-serial", help="D435i serial number")
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
    parser.add_argument("--greeting-retry-s", type=float, default=5.0)
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


def _print_action(result: SkillResult) -> None:
    print(
        json.dumps(
            {"type": "skill_result", **result.to_dict()},
            ensure_ascii=False,
        ),
        flush=True,
    )


async def run_perception_loop(
    *,
    camera: RealSensePersonDetector,
    runtime: SkillRuntime,
    world_state: WorldState,
    once: bool = False,
) -> int:
    greeting = PersonGreetingLoop(runtime, world_state)

    while True:
        observation = await asyncio.to_thread(camera.capture)
        _print_observation(observation)
        result = await greeting.process(observation)
        if result is not None:
            _print_action(result)
            if once and not result.success:
                return 1
        if once:
            return 0


async def _run(args: argparse.Namespace) -> int:
    hardware_robot: UnitreeG1Adapter | None = None
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
    camera = RealSensePersonDetector(
        serial=args.camera_serial,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_timeout_ms=args.frame_timeout_ms,
        min_score=args.min_score,
        max_distance_m=args.max_distance_m,
    )
    world_state = WorldState(
        absence_reset_s=args.absence_reset_s,
        greeting_retry_s=args.greeting_retry_s,
    )

    try:
        if hardware_robot is not None:
            await hardware_robot.connect()
        await asyncio.to_thread(camera.open)
        return await run_perception_loop(
            camera=camera,
            runtime=runtime,
            world_state=world_state,
            once=args.once,
        )
    finally:
        try:
            await asyncio.to_thread(camera.close)
        finally:
            if hardware_robot is not None:
                await hardware_robot.close()


def main() -> int:
    try:
        return asyncio.run(_run(parse_args()))
    except KeyboardInterrupt:
        return 130
    except (PerceptionError, RobotCommandError, RuntimeError, ValueError) as exc:
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

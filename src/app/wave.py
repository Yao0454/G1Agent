"""Run the wave skill directly, without an Agent or language model."""

from __future__ import annotations

import argparse
import asyncio
import json

from core.models import SkillResult
from core.runtime import SkillRuntime
from core.types import FailureCode, SkillStatus
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
        "--network", default="", help="Unitree DDS interface, e.g. eth0"
    )
    parser.add_argument("--domain-id", type=int, default=0)
    return parser.parse_args()


async def run_wave(
    *,
    hardware: bool,
    network_interface: str = "",
    domain_id: int = 0,
) -> SkillResult:
    hardware_robot: UnitreeG1Adapter | None = None
    robot: RobotAdapter

    if hardware:
        hardware_robot = UnitreeG1Adapter(
            UnitreeG1Config(
                network_interface=network_interface,
                domain_id=domain_id,
            )
        )
        robot = hardware_robot
    else:
        robot = SimulatedRobotAdapter()

    runtime = SkillRuntime(robot)
    runtime.register(WaveSkill())

    try:
        if hardware_robot is not None:
            await hardware_robot.connect()
        return await runtime.execute("wave", arm="right")
    finally:
        if hardware_robot is not None:
            await hardware_robot.close()


async def _run(args: argparse.Namespace) -> int:
    try:
        result = await run_wave(
            hardware=args.hardware,
            network_interface=args.network,
            domain_id=args.domain_id,
        )
    except (RobotCommandError, RuntimeError) as exc:
        result = SkillResult.fail(
            SkillStatus.FAILED,
            str(exc),
            failure_code=FailureCode.ROBOT_ERROR,
        )

    print(json.dumps(result.to_dict(), ensure_ascii=False, default=str))
    return 0 if result.success else 1


def main() -> int:
    return asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

"""Per-invocation dependencies passed to robot skills."""

from dataclasses import dataclass, field

from robot.base import RobotAdapter


@dataclass(slots=True)
class SkillContext:
    robot: RobotAdapter
    execution_id: str
    runtime_data: dict[str, object] = field(default_factory=dict)

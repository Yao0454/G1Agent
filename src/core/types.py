"""Shared enums for the robot skill runtime."""

from enum import Enum


class SkillStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    PRECONDITION_FAILED = "precondition_failed"
    VERIFICATION_FAILED = "verification_failed"

    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

    SAFETY_STOP = "safety_stop"


class FailureCode(str, Enum):
    UNKNOWN = "unknown"
    INVALID_ARGUMENTS = "invalid_arguments"
    PRECONDITION_NOT_MET = "precondition_not_met"

    ROBOT_ERROR = "robot_error"
    EXECUTION_ERROR = "execution_error"

    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

    RESOURCE_BUSY = "resource_busy"
    SAFETY_REJECTED = "safety_rejected"

    VERIFICATION_FAILED = "verification_failed"


class ExecutionPhase(str, Enum):
    CREATED = "created"

    VALIDATING = "validating"
    WAITING_RESOURCE = "waiting_resource"

    PRECONDITION = "precondition"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    CLEANUP = "cleanup"

    FINISHED = "finished"

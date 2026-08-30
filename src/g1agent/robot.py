"""A deliberately small, safe Unitree G1 action dispatcher."""

from __future__ import annotations

import asyncio
import time
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


@dataclass(frozen=True, slots=True)
class ActionResult:
    action: str
    ok: bool
    status: int | None = None
    detail: str = ""


class Robot:
    """Dispatch a finite action set to Unitree SDK2 or a console dry-run.

    ``hardware=False`` is the default. This means the complete voice/brain/TTS
    loop can be rehearsed safely on a laptop. Pass ``--hardware`` only on the
    Jetson connected to a G1, after checking the area around the robot.
    """

    def __init__(
        self, hardware: bool = False, network: str = "", timeout: float = 10.0
    ) -> None:
        self.hardware = hardware
        self.network = network
        self.timeout = timeout
        self._lock = asyncio.Lock()
        self._connected = False
        self._channel: Any = None
        self._loco: Any = None
        self._arm: Any = None

    def connect(self) -> None:
        if not self.hardware or self._connected:
            return
        try:
            from unitree_sdk2_cpp import channel
            from unitree_sdk2_cpp.robot.g1 import G1ArmActionClient, LocoClient

            channel.initialize(0, self.network)
            self._channel = channel
            self._loco = LocoClient()
            self._loco.set_timeout(self.timeout)
            self._loco.init()
            self._arm = G1ArmActionClient()
            self._arm.set_timeout(self.timeout)
            self._arm.init()
            status = int(self._loco.start())
            if status != 0:
                raise RuntimeError(f"切换 G1 FSM 失败，状态码：{status}")
            deadline = time.monotonic() + self.timeout
            while True:
                status, fsm_id = self._loco.get_fsm_id()
                if int(status) != 0:
                    raise RuntimeError(f"读取 G1 FSM 失败，状态码：{status}")
                if int(fsm_id) == 500:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"G1 FSM 未切换到 500，当前为 {fsm_id}")
                time.sleep(0.2)
            self._connected = True
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            if self._channel is not None:
                self._channel.release()
                self._channel = None
            raise RuntimeError(f"Unitree SDK 初始化失败：{exc}") from exc

    async def execute(self, action: str) -> ActionResult:
        action = action.strip().lower()
        if action not in SUPPORTED_ACTIONS:
            return ActionResult(action=action, ok=False, detail="unknown action")
        if action == "none":
            return ActionResult(action=action, ok=True, detail="no-op")

        async with self._lock:
            return await run_blocking(self._execute_sync, action)

    def _execute_sync(self, action: str) -> ActionResult:
        if not self.hardware:
            print(f"[robot dry-run] {action}")
            return ActionResult(action=action, ok=True, detail="dry-run")
        if not self._connected:
            return ActionResult(
                action=action, ok=False, detail="robot is not connected"
            )

        try:
            status = self._call_action(action)
            status_int = int(status)
            if status_int != 0:
                print(f"[robot] {action} failed with SDK status {status_int}")
            return ActionResult(action=action, ok=status_int == 0, status=status_int)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return ActionResult(action=action, ok=False, detail=str(exc))

    def _call_action(self, action: str) -> int:
        loco = self._loco
        arm = self._arm
        if action == "wave":
            return loco.wave_hand()
        if action == "shake_hand":
            return loco.shake_hand()
        if action == "stand":
            return loco.stand_up()
        if action == "sit":
            return loco.sit()
        if action == "move_forward":
            return loco.set_velocity(0.20, 0.0, 0.0, 0.7)
        if action == "turn_left":
            return loco.set_velocity(0.0, 0.0, 0.45, 0.7)
        if action == "turn_right":
            return loco.set_velocity(0.0, 0.0, -0.45, 0.7)
        if action == "stop":
            stop_status = int(loco.stop_move())
            try:
                arm_status = int(arm.stop_custom_action())
            except (OSError, RuntimeError, TypeError, ValueError):
                arm_status = 0
            return stop_status if stop_status != 0 else arm_status
        # These are exhibition actions. The SDK's custom action service resolves
        # the names configured on the robot; an unknown name returns a status.
        return arm.execute_action(action)

    def close(self) -> None:
        if self._connected and self._channel is not None:
            self._channel.release()
        self._connected = False
        self._channel = None


# Naming alias for callers that prefer to make the dispatch boundary explicit.
ActionExecutor = Robot

"""Direct adapter for the Unitree SDK2 Python bindings."""

from __future__ import annotations

import asyncio
import importlib
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

from .base import RobotCommandError, RobotState

logger = logging.getLogger(__name__)


class ChannelApi(Protocol):
    def initialize(self, domain_id: int = 0, network_interface: str = "") -> None: ...

    def release(self) -> None: ...


class G1LocoClientApi(Protocol):
    def set_timeout(self, seconds: float) -> None: ...

    def init(self) -> None: ...

    def get_fsm_id(self) -> tuple[int, int]: ...

    def wave_hand(self, turn_flag: bool = False) -> int: ...

    def stop_move(self) -> int: ...

    def move(
        self,
        vx: float,
        vy: float,
        vyaw: float,
        continous_move: bool,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class UnitreeBindings:
    channel: ChannelApi
    create_loco_client: Callable[[], G1LocoClientApi]


@dataclass(frozen=True, slots=True)
class UnitreeG1Config:
    network_interface: str = ""
    domain_id: int = 0
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if self.domain_id < 0:
            raise ValueError("domain_id must not be negative")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be greater than zero")


class UnitreeG1Adapter:
    """Own the DDS channel and G1 locomotion client used by robot skills.

    Connection only initializes communication. It deliberately does not call
    ``start()`` or any other motion command. Likewise, ``close()`` only releases
    DDS resources; it is not a mechanical stop or physical emergency stop.
    """

    def __init__(
        self,
        config: UnitreeG1Config | None = None,
        *,
        bindings: UnitreeBindings | None = None,
    ) -> None:
        self.config = config or UnitreeG1Config()
        self._bindings = bindings
        self._loco: G1LocoClientApi | None = None
        self._channel_ready = False
        self._lock = asyncio.Lock()
        self._native_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._channel_ready and self._loco is not None

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            await asyncio.to_thread(self._connect_sync)

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._close_sync)

    async def get_state(self) -> RobotState:
        async with self._lock:
            if not self.connected:
                return RobotState(hardware=True, connected=False)
            fsm_id = await self._run_native("get_fsm_id", self._get_fsm_id_sync)
            return RobotState(
                hardware=True,
                connected=True,
                details={"fsm_id": fsm_id},
            )

    async def stop(self) -> None:
        async with self._lock:
            await self._run_native("stop_move", self._stop_sync)

    async def wave(self, arm: str) -> None:
        if arm != "right":
            raise RobotCommandError(f"unsupported wave arm: {arm}")
        async with self._lock:
            await self._run_native("wave_hand", self._wave_sync)

    async def move_velocity(
        self,
        forward_m_s: float,
        lateral_m_s: float,
        yaw_rad_s: float,
    ) -> None:
        async with self._lock:
            await self._run_native(
                "move",
                lambda: self._move_sync(
                    forward_m_s,
                    lateral_m_s,
                    yaw_rad_s,
                ),
            )

    @staticmethod
    async def _run_native[ResultT](
        operation: str,
        function: Callable[[], ResultT],
    ) -> ResultT:
        try:
            return await asyncio.to_thread(function)
        except RobotCommandError:
            raise
        except Exception as exc:
            raise RobotCommandError(f"{operation} failed: {exc}") from exc

    def _connect_sync(self) -> None:
        with self._native_lock:
            if self.connected:
                return
            bindings = self._bindings or self._load_bindings()
            channel_ready = False
            try:
                bindings.channel.initialize(
                    self.config.domain_id,
                    self.config.network_interface,
                )
                channel_ready = True
                client = bindings.create_loco_client()
                client.set_timeout(self.config.timeout_s)
                client.init()
            except Exception as exc:
                if channel_ready:
                    try:
                        bindings.channel.release()
                    except Exception:
                        logger.exception(
                            "failed to release Unitree DDS after connect failure"
                        )
                raise RobotCommandError(f"failed to connect to G1: {exc}") from exc

            self._bindings = bindings
            self._loco = client
            self._channel_ready = True

    def _close_sync(self) -> None:
        with self._native_lock:
            bindings = self._bindings
            self._loco = None
            if not self._channel_ready or bindings is None:
                return
            self._channel_ready = False
            try:
                bindings.channel.release()
            except Exception as exc:
                raise RobotCommandError(
                    f"failed to release Unitree DDS: {exc}"
                ) from exc

    def _get_fsm_id_sync(self) -> int:
        with self._native_lock:
            client = self._require_loco()
            status, fsm_id = client.get_fsm_id()
            self._require_success("get_fsm_id", status)
            return fsm_id

    def _stop_sync(self) -> None:
        with self._native_lock:
            status = self._require_loco().stop_move()
            self._require_success("stop_move", status)

    def _wave_sync(self) -> None:
        with self._native_lock:
            status = self._require_loco().wave_hand(False)
            self._require_success("wave_hand", status)

    def _move_sync(
        self,
        forward_m_s: float,
        lateral_m_s: float,
        yaw_rad_s: float,
    ) -> None:
        with self._native_lock:
            status = self._require_loco().move(
                forward_m_s,
                lateral_m_s,
                yaw_rad_s,
                False,
            )
            self._require_success("move", status)

    def _require_loco(self) -> G1LocoClientApi:
        if self._loco is None or not self._channel_ready:
            raise RobotCommandError("G1 adapter is not connected")
        return self._loco

    @staticmethod
    def _require_success(operation: str, status: int) -> None:
        if status != 0:
            raise RobotCommandError(f"{operation} failed with SDK status {status}")

    @staticmethod
    def _load_bindings() -> UnitreeBindings:
        try:
            channel_module = importlib.import_module("unitree_sdk2_cpp.channel")
            g1_module = importlib.import_module("unitree_sdk2_cpp.robot.g1")
            channel = cast(ChannelApi, cast(object, channel_module))
            factory = cast(
                Callable[[], G1LocoClientApi],
                cast(object, getattr(g1_module, "LocoClient")),  # noqa: B009
            )
            return UnitreeBindings(channel=channel, create_loco_client=factory)
        except (ImportError, AttributeError) as exc:
            raise RobotCommandError(
                "Unitree SDK2 Python bindings are unavailable; install "
                "~/unitree_sdk2/unitree_sdk2_bindings on the Linux robot host"
            ) from exc

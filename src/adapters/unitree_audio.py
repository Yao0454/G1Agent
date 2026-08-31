"""Unitree G1 AudioClient output for speaking Agent responses."""

from __future__ import annotations

import asyncio
import importlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast


class AudioOutputError(RuntimeError):
    """Raised when G1 audio initialization or speech fails."""


class ChannelConnection(Protocol):
    @property
    def connected(self) -> bool: ...


class SpeechOutput(Protocol):
    async def speak(self, text: str) -> None: ...


class AudioClientApi(Protocol):
    def set_timeout(self, seconds: float) -> None: ...

    def init(self) -> None: ...

    def tts_maker(self, text: str, speaker_id: int) -> int: ...


@dataclass(frozen=True, slots=True)
class UnitreeAudioBindings:
    create_audio_client: Callable[[], AudioClientApi]


class UnitreeAudioOutput:
    """Use AudioClient on a DDS channel owned by the robot adapter.

    This adapter never initializes or releases the process-global Unitree channel.
    The supplied connection must remain connected for this object's lifetime.
    """

    def __init__(
        self,
        connection: ChannelConnection,
        *,
        speaker_id: int = 0,
        timeout_s: float = 10.0,
        bindings: UnitreeAudioBindings | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("audio timeout_s must be greater than zero")
        self.connection = connection
        self.speaker_id = speaker_id
        self.timeout_s = timeout_s
        self._bindings = bindings
        self._client: AudioClientApi | None = None
        self._lock = asyncio.Lock()
        self._native_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self.connection.connected and self._client is not None

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            if not self.connection.connected:
                raise AudioOutputError(
                    "Unitree DDS must be connected before AudioClient initialization"
                )
            await asyncio.to_thread(self._connect_sync)

    async def close(self) -> None:
        async with self._lock:
            self._client = None

    async def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        async with self._lock:
            if not self.connected:
                raise AudioOutputError("AudioClient is not connected")
            await asyncio.to_thread(self._speak_sync, text)

    def _connect_sync(self) -> None:
        with self._native_lock:
            if self.connected:
                return
            try:
                bindings = self._bindings or self._load_bindings()
                client = bindings.create_audio_client()
                client.set_timeout(self.timeout_s)
                client.init()
            except Exception as exc:
                raise AudioOutputError(f"failed to initialize AudioClient: {exc}") from exc
            self._bindings = bindings
            self._client = client

    def _speak_sync(self, text: str) -> None:
        with self._native_lock:
            client = self._client
            if client is None or not self.connection.connected:
                raise AudioOutputError("AudioClient is not connected")
            try:
                status = client.tts_maker(text, self.speaker_id)
            except Exception as exc:
                raise AudioOutputError(f"AudioClient TTS failed: {exc}") from exc
            if status != 0:
                raise AudioOutputError(
                    f"AudioClient TTS failed with SDK status {status}"
                )

    @staticmethod
    def _load_bindings() -> UnitreeAudioBindings:
        try:
            g1_module = importlib.import_module("unitree_sdk2_cpp.robot.g1")
            factory = cast(
                Callable[[], AudioClientApi],
                cast(object, getattr(g1_module, "AudioClient")),  # noqa: B009
            )
            return UnitreeAudioBindings(create_audio_client=factory)
        except (ImportError, AttributeError) as exc:
            raise AudioOutputError(
                "Unitree AudioClient is unavailable; install "
                "~/unitree_sdk2/unitree_sdk2_bindings on the robot host"
            ) from exc

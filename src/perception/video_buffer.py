"""Thread-safe sliding window for recent camera frames."""

from __future__ import annotations

import threading
from collections import deque

from .models import CameraFrame


class VideoBuffer:
    def __init__(self, *, window_s: float = 2.0, max_frames: int = 60) -> None:
        if window_s <= 0:
            raise ValueError("video window must be greater than zero")
        if max_frames <= 0:
            raise ValueError("max frames must be greater than zero")
        self.window_s = window_s
        self._frames: deque[CameraFrame] = deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)

    def push(self, frame: CameraFrame) -> None:
        with self._lock:
            self._frames.append(frame)
            cutoff = frame.observed_at_s - self.window_s
            while self._frames and self._frames[0].observed_at_s < cutoff:
                self._frames.popleft()

    def sample(self, count: int = 8) -> tuple[CameraFrame, ...]:
        if count <= 0:
            raise ValueError("sample count must be greater than zero")
        with self._lock:
            frames = tuple(self._frames)
        if len(frames) <= count:
            return frames
        if count == 1:
            return (frames[-1],)
        last_index = len(frames) - 1
        indices = [round(index * last_index / (count - 1)) for index in range(count)]
        return tuple(frames[index] for index in indices)

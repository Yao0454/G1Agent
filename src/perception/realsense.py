"""Direct USB Intel RealSense D435i person detector."""

from __future__ import annotations

import importlib
import logging
import math
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from .models import PerceptionResult

logger = logging.getLogger(__name__)


class PerceptionError(RuntimeError):
    """Raised when camera capture or person detection fails."""


class _RealSenseFrame(Protocol):
    def get_data(self) -> object: ...

    def get_width(self) -> int: ...

    def get_height(self) -> int: ...


class _RealSenseDepthFrame(_RealSenseFrame, Protocol):
    def get_distance(self, x: int, y: int) -> float: ...


class _RealSenseFrames(Protocol):
    def get_color_frame(self) -> _RealSenseFrame | None: ...

    def get_depth_frame(self) -> _RealSenseDepthFrame | None: ...


class _RealSensePipeline(Protocol):
    def start(self, config: object) -> object: ...

    def wait_for_frames(self, timeout_ms: int) -> _RealSenseFrames: ...

    def stop(self) -> None: ...


class _RealSenseConfig(Protocol):
    def enable_device(self, serial: str) -> None: ...

    def enable_stream(self, *args: object) -> None: ...


class _RealSenseAlign(Protocol):
    def process(self, frames: _RealSenseFrames) -> _RealSenseFrames: ...


class _RealSenseStreamValues(Protocol):
    color: object
    depth: object


class _RealSenseFormatValues(Protocol):
    bgr8: object
    z16: object


class _RealSenseApi(Protocol):
    pipeline: Callable[[], _RealSensePipeline]
    config: Callable[[], _RealSenseConfig]
    align: Callable[[object], _RealSenseAlign]
    stream: _RealSenseStreamValues
    format: _RealSenseFormatValues


class _NumpyApi(Protocol):
    def asanyarray(self, value: object) -> object: ...


class _HogDescriptor(Protocol):
    def setSVMDetector(self, detector: object) -> None: ...

    def detectMultiScale(
        self,
        image: object,
        *,
        winStride: tuple[int, int],
        padding: tuple[int, int],
        scale: float,
    ) -> tuple[Sequence[Sequence[int]], Sequence[float]]: ...


class _OpenCvApi(Protocol):
    HOGDescriptor: Callable[[], _HogDescriptor]
    HOGDescriptor_getDefaultPeopleDetector: Callable[[], object]


@dataclass(frozen=True, slots=True)
class RealSenseBindings:
    realsense: _RealSenseApi
    numpy: _NumpyApi
    opencv: _OpenCvApi


class RealSensePersonDetector:
    """Capture aligned color/depth frames and detect people in RGB images."""

    def __init__(
        self,
        *,
        serial: str | None = None,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        frame_timeout_ms: int = 5000,
        min_score: float = 0.5,
        max_distance_m: float | None = 4.0,
        bindings: RealSenseBindings | None = None,
    ) -> None:
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("camera width, height, and fps must be positive")
        if frame_timeout_ms <= 0:
            raise ValueError("frame_timeout_ms must be positive")
        if max_distance_m is not None and max_distance_m <= 0:
            raise ValueError("max_distance_m must be positive")

        self.serial = serial
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_timeout_ms = frame_timeout_ms
        self.min_score = min_score
        self.max_distance_m = max_distance_m
        self._bindings = bindings
        self._pipeline: _RealSensePipeline | None = None
        self._align: _RealSenseAlign | None = None
        self._hog: _HogDescriptor | None = None
        self._lock = threading.Lock()

    @property
    def opened(self) -> bool:
        return self._pipeline is not None

    def open(self) -> None:
        with self._lock:
            if self.opened:
                return
            bindings = self._bindings or self._load_bindings()
            pipeline = bindings.realsense.pipeline()
            config = bindings.realsense.config()
            if self.serial:
                config.enable_device(self.serial)
            config.enable_stream(
                bindings.realsense.stream.depth,
                self.width,
                self.height,
                bindings.realsense.format.z16,
                self.fps,
            )
            config.enable_stream(
                bindings.realsense.stream.color,
                self.width,
                self.height,
                bindings.realsense.format.bgr8,
                self.fps,
            )

            try:
                pipeline.start(config)
                align = bindings.realsense.align(bindings.realsense.stream.color)
                hog = bindings.opencv.HOGDescriptor()
                hog.setSVMDetector(
                    bindings.opencv.HOGDescriptor_getDefaultPeopleDetector()
                )
            except Exception as exc:
                try:
                    pipeline.stop()
                except Exception:
                    logger.exception(
                        "failed to stop RealSense pipeline after open failure"
                    )
                raise PerceptionError(f"failed to open RealSense D435i: {exc}") from exc

            self._bindings = bindings
            self._pipeline = pipeline
            self._align = align
            self._hog = hog

    def close(self) -> None:
        with self._lock:
            pipeline = self._pipeline
            self._pipeline = None
            self._align = None
            self._hog = None
            if pipeline is None:
                return
            try:
                pipeline.stop()
            except Exception as exc:
                raise PerceptionError(f"failed to stop RealSense D435i: {exc}") from exc

    def capture(self) -> PerceptionResult:
        with self._lock:
            pipeline = self._pipeline
            align = self._align
            hog = self._hog
            bindings = self._bindings
            if pipeline is None or align is None or hog is None or bindings is None:
                raise PerceptionError("RealSense D435i is not open")

            try:
                frames = pipeline.wait_for_frames(self.frame_timeout_ms)
                aligned_frames = align.process(frames)
                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()
                if color_frame is None or depth_frame is None:
                    raise PerceptionError("D435i returned an incomplete frame set")

                image = bindings.numpy.asanyarray(color_frame.get_data())
                rectangles, scores = hog.detectMultiScale(
                    image,
                    winStride=(8, 8),
                    padding=(8, 8),
                    scale=1.05,
                )
                return self._build_result(
                    color_frame,
                    depth_frame,
                    rectangles,
                    scores,
                )
            except PerceptionError:
                raise
            except Exception as exc:
                raise PerceptionError(f"D435i capture failed: {exc}") from exc

    def _build_result(
        self,
        color_frame: _RealSenseFrame,
        depth_frame: _RealSenseDepthFrame,
        rectangles: Sequence[Sequence[int]],
        scores: Sequence[float],
    ) -> PerceptionResult:
        accepted_scores: list[float] = []
        distances: list[float] = []
        width = color_frame.get_width()
        height = color_frame.get_height()

        for rectangle, score_value in zip(rectangles, scores, strict=False):
            score = float(score_value)
            if score < self.min_score or len(rectangle) < 4:
                continue
            x, y, box_width, box_height = (
                int(rectangle[0]),
                int(rectangle[1]),
                int(rectangle[2]),
                int(rectangle[3]),
            )
            center_x = min(max(x + box_width // 2, 0), width - 1)
            center_y = min(max(y + box_height // 2, 0), height - 1)
            distance = float(depth_frame.get_distance(center_x, center_y))
            if distance > 0:
                if self.max_distance_m is not None and distance > self.max_distance_m:
                    continue
                distances.append(distance)
            accepted_scores.append(score)

        confidence = (
            self._score_to_confidence(max(accepted_scores)) if accepted_scores else None
        )
        return PerceptionResult(
            observed_at_s=time.monotonic(),
            person_count=len(accepted_scores),
            nearest_person_distance_m=min(distances) if distances else None,
            confidence=confidence,
            source=f"realsense:{self.serial or 'D435i'}",
        )

    @staticmethod
    def _score_to_confidence(score: float) -> float:
        if score >= 0:
            return 1.0 / (1.0 + math.exp(-score))
        exp_score = math.exp(score)
        return exp_score / (1.0 + exp_score)

    @staticmethod
    def _load_bindings() -> RealSenseBindings:
        try:
            realsense_module = importlib.import_module("pyrealsense2")
            numpy_module = importlib.import_module("numpy")
            opencv_module = importlib.import_module("cv2")
        except ImportError as exc:
            raise PerceptionError(
                "D435i dependencies are unavailable; install pyrealsense2, numpy, "
                "and opencv-python-headless on the camera host"
            ) from exc
        return RealSenseBindings(
            realsense=cast(_RealSenseApi, cast(object, realsense_module)),
            numpy=cast(_NumpyApi, cast(object, numpy_module)),
            opencv=cast(_OpenCvApi, cast(object, opencv_module)),
        )

"""Sliding-window video policy backed by a local multimodal model."""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from adapters.unitree_audio import SpeechOutput
from core.models import SkillArgs, SkillResult
from core.runtime import SkillRuntime
from core.skill import RobotSkill
from perception import CameraFrame, VideoBuffer
from robot import RobotState

from .decision import AgentDecision, DecisionAgentError

DEFAULT_VISION_MODEL = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
DEFAULT_VISION_GOAL = (
    "Respond to explicit social gestures. Prefer handshake for an extended "
    "hand, and do not wave merely because a person is visible."
)

_CANONICAL_SKILL_NAMES = {
    "wave_hand": "wave",
    "shake_hand": "handshake",
    "stop_move": "stop",
}
_HANDSHAKE_CONFIRMATION_DISTANCE_M = 0.5
_HANDSHAKE_CONFIRMATION_MAX_AGE_S = 1.0
_RECOVERED_HANDSHAKE_CONFIRMATION_MAX_AGE_S = 5.0

_VISION_SYSTEM_PROMPT = """You are the real-time visual decision module for a Unitree G1.
The supplied images are ordered frames sampled from the robot's most recent
video window. Decide only the robot's next action now.

Output exactly one compact JSON object. action is required and must be
execute_skill, execute_and_speak, speak, continue, interrupt, or ignore.
Omit unused skill, arguments, speech, and reason fields. Use continue while the
current behavior should keep running. Use interrupt only when the current
behavior must stop immediately. Keep reason under four words when included.
The skill catalog is reference documentation. Never copy catalog definitions
into arguments. arguments contains only actual values for the one selected
skill, for example {"arm":"right"} or {"distance_m":0.2}.
If a person clearly extends a hand toward the robot to shake hands, select the
handshake skill immediately; do not wait for another confirmation. A handshake
offer usually reaches toward the camera around waist or lower-chest height. A
high five is normally a raised open palm around shoulder/head height. Use motion
across the window when multiple frames exist, and pose/height when there is only
one frame.
Decision priority is safety interrupt, handshake, high five, explicit wave,
then ignore. Merely seeing a person is not a reason to wave or speak. Select
wave only when the person's hand is visibly waving side-to-side or they make an
unambiguous greeting gesture. If policy_context says wave was recently selected,
the person is already greeted; do not wave again, but still select handshake if
they now extend a hand.
For no response, use action ignore. For a handshake, use action execute_skill
and skill handshake. Usually omit arguments so the registered safe defaults are
used. Never output JSON Schema objects or keys such as type, default, const,
minimum, or maximum inside arguments.
Do not describe the video and do not predict far into the future. Use only the
registered skills and their argument schemas. Keep speech brief.
"""


class VisionModelInvoker(Protocol):
    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object: ...


class OllamaVisionInvoker:
    """Send an ordered frame set to a local Ollama multimodal model."""

    def __init__(
        self,
        model_name: str,
        *,
        base_url: str | None = None,
    ) -> None:
        ollama = importlib.import_module("ollama")
        self.model_name = model_name
        self._client = ollama.AsyncClient(host=base_url)

    async def warmup(self) -> None:
        await self._client.show(self.model_name)

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        encoded_frames = [self._as_bytes(frame) for frame in frames]
        response = await self._client.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": encoded_frames,
                }
            ],
            format=AgentDecision.model_json_schema(),
            options={"temperature": 0.1, "num_predict": 160},
            keep_alive="30m",
        )
        message = response.get("message") if isinstance(response, Mapping) else None
        if isinstance(message, Mapping):
            return str(message.get("content", ""))
        response_message = getattr(response, "message", None)
        return str(getattr(response_message, "content", ""))

    @staticmethod
    def _as_bytes(frame: object) -> bytes:
        if isinstance(frame, bytes):
            return frame
        if isinstance(frame, (bytearray, memoryview)):
            return bytes(frame)
        image = TransformersVisionInvoker._to_pil_image(frame)
        output = io.BytesIO()
        image_value: Any = image
        image_value.save(output, format="JPEG", quality=80)
        return output.getvalue()


class TransformersVisionInvoker:
    """Lazy Transformers backend so non-vision entry points stay lightweight."""

    def __init__(
        self,
        model_name: str = DEFAULT_VISION_MODEL,
        *,
        max_new_tokens: int = 40,
    ) -> None:
        if max_new_tokens <= 0:
            raise ValueError("max new tokens must be greater than zero")
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self._processor: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None
        self._device: str | None = None
        self._load_lock = asyncio.Lock()

    async def warmup(self) -> None:
        await self._ensure_loaded()

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        if not frames:
            raise ValueError("vision model requires at least one frame")
        await self._ensure_loaded()
        return await asyncio.to_thread(self._generate, tuple(frames), prompt)

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            try:
                await asyncio.to_thread(self._load)
            except (ImportError, ModuleNotFoundError) as exc:
                raise DecisionAgentError(
                    "vision dependencies are unavailable; install the vision extra "
                    "and a Jetson-compatible PyTorch build"
                ) from exc

    def _load(self) -> None:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        processor_class = transformers.AutoProcessor
        model_class = transformers.AutoModelForImageTextToText
        processor = processor_class.from_pretrained(self.model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = model_class.from_pretrained(
            self.model_name,
            dtype=dtype,
        )
        model.to(device)
        model.eval()
        self._torch = torch
        self._processor = processor
        self._model = model
        self._device = device

    def _generate(self, frames: Sequence[object], prompt: str) -> str:
        processor = self._processor
        model = self._model
        torch = self._torch
        device = self._device
        if processor is None or model is None or torch is None or device is None:
            raise RuntimeError("vision model was not loaded")

        images = [self._to_pil_image(frame) for frame in frames]
        content: list[dict[str, object]] = [
            {"type": "video", "video": images},
            {"type": "text", "text": prompt},
        ]
        messages = [{"role": "user", "content": content}]
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            do_sample_frames=False,
        )
        inputs = inputs.to(device)
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        input_length = inputs["input_ids"].shape[1]
        output_ids = generated[:, input_length:]
        decoded = processor.batch_decode(output_ids, skip_special_tokens=True)
        if not decoded:
            raise RuntimeError("vision model returned no text")
        return str(decoded[0]).strip()

    @staticmethod
    def _to_pil_image(frame: object) -> object:
        image_module = importlib.import_module("PIL.Image")
        if isinstance(frame, (bytes, bytearray, memoryview)):
            image = image_module.open(io.BytesIO(bytes(frame)))
            return image.convert("RGB")
        if hasattr(frame, "__array_interface__"):
            return image_module.fromarray(frame).convert("RGB")
        raise TypeError(f"unsupported video frame type: {type(frame).__name__}")


def _skill_catalog_payload(
    skill_catalog: Sequence[RobotSkill[SkillArgs]],
) -> list[dict[str, object]]:
    catalog: list[dict[str, object]] = []
    registered_names = {skill.metadata.name for skill in skill_catalog}
    for skill in skill_catalog:
        canonical_name = _CANONICAL_SKILL_NAMES.get(skill.metadata.name)
        if canonical_name is not None and canonical_name in registered_names:
            continue
        schema = skill.args_model.model_json_schema()
        raw_properties = schema.get("properties", {})
        raw_required = schema.get("required", [])
        required_names = {
            name for name in raw_required if isinstance(name, str)
        } if isinstance(raw_required, list) else set()
        arguments: dict[str, object] = {}
        if isinstance(raw_properties, Mapping):
            for name, raw_descriptor in raw_properties.items():
                if not isinstance(name, str) or not isinstance(
                    raw_descriptor, Mapping
                ):
                    continue
                if "default" in raw_descriptor:
                    arguments[name] = raw_descriptor["default"]
                elif "const" in raw_descriptor:
                    arguments[name] = raw_descriptor["const"]
                elif name in required_names:
                    arguments[name] = "<required>"
        catalog.append(
            {
                "name": skill.metadata.name,
                "description": skill.metadata.description,
                "argument_defaults": arguments,
                "required_arguments": sorted(required_names),
                "interruptible": skill.metadata.interruptible,
            }
        )
    return catalog


def _recover_safe_noop(text: str) -> AgentDecision | None:
    safe_actions = set(
        re.findall(
            r'["\']action["\']\s*:\s*["\'](ignore|continue)["\']',
            text,
        )
    )
    if len(safe_actions) != 1:
        return None
    return AgentDecision(
        action=safe_actions.pop(),
        reason="recovered safe no-op from malformed model JSON",
    )


def _recover_truncated_skill_decision(
    text: str,
    recoverable_skills: set[str],
) -> AgentDecision | None:
    action_match = re.search(
        r'["\']action["\']\s*:\s*["\']execute_skill["\']',
        text,
    )
    skill_match = re.search(
        r'["\']skill["\']\s*:\s*["\']([a-zA-Z0-9_-]+)["\']',
        text,
    )
    if action_match is None or skill_match is None:
        return None
    skill_name = skill_match.group(1)
    if skill_name not in recoverable_skills:
        return None
    return AgentDecision(
        action="execute_skill",
        skill=skill_name,
        reason="recovered truncated model JSON",
    )


def _sanitize_visual_noop_payload(value: object) -> object:
    """Discard hallucinated arguments from an otherwise explicit visual no-op."""
    if not isinstance(value, Mapping):
        return value
    payload = dict(value)
    action = payload.get("action")
    if not isinstance(action, str) or action.strip() not in {"ignore", "continue"}:
        return payload
    if _has_nonempty_visual_value(payload.get("skill")):
        return payload
    if _has_nonempty_visual_value(payload.get("speech")):
        return payload
    payload["action"] = action.strip()
    payload["skill"] = None
    payload["arguments"] = {}
    payload["speech"] = None
    return payload


def _has_nonempty_visual_value(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


class VisionDecisionAgent:
    def __init__(
        self,
        *,
        model_name: str = DEFAULT_VISION_MODEL,
        invoker: VisionModelInvoker | None = None,
        timeout_s: float = 20.0,
        goal: str = DEFAULT_VISION_GOAL,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("vision decision timeout must be greater than zero")
        if not goal.strip():
            raise ValueError("vision policy goal must not be empty")
        self.model_name = model_name
        self.timeout_s = timeout_s
        self.goal = goal.strip()
        self._invoker = invoker or TransformersVisionInvoker(model_name)

    async def warmup(self) -> None:
        warmup = getattr(self._invoker, "warmup", None)
        if callable(warmup):
            await warmup()

    async def close(self) -> None:
        close = getattr(self._invoker, "close", None)
        if callable(close):
            await close()

    @property
    def last_metrics(self) -> Mapping[str, object]:
        metrics = getattr(self._invoker, "last_metrics", {})
        return dict(metrics) if isinstance(metrics, Mapping) else {}

    async def decide(
        self,
        frames: Sequence[CameraFrame],
        robot_state: RobotState,
        skill_catalog: Sequence[RobotSkill[SkillArgs]],
        *,
        policy_context: Mapping[str, object] | None = None,
    ) -> AgentDecision:
        if not frames:
            return AgentDecision(action="ignore", reason="video window is empty")
        payload = {
            "goal": self.goal,
            "video_window": {
                "frame_count": len(frames),
                "start_s": frames[0].observed_at_s,
                "end_s": frames[-1].observed_at_s,
                "duration_s": max(
                    0.0,
                    frames[-1].observed_at_s - frames[0].observed_at_s,
                ),
            },
            "robot_state": {
                "hardware": robot_state.hardware,
                "connected": robot_state.connected,
                "details": robot_state.details,
            },
            "policy_context": dict(policy_context or {}),
            "skill_catalog": _skill_catalog_payload(skill_catalog),
        }
        prompt = (
            f"{_VISION_SYSTEM_PROMPT}\nRuntime context:\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )
        try:
            async with asyncio.timeout(self.timeout_s):
                output = await self._invoker.ainvoke(
                    [frame.rgb for frame in frames],
                    prompt,
                )
            decision = self._parse_output(
                output,
                recoverable_skills=self._recoverable_skill_names(skill_catalog),
            )
        except TimeoutError as exc:
            raise DecisionAgentError(
                f"Vision Decision Agent timed out after {self.timeout_s:g} seconds"
            ) from exc
        except DecisionAgentError:
            raise
        except Exception as exc:
            raise DecisionAgentError(
                f"Vision Decision Agent invocation failed: {exc}"
            ) from exc

        skill_names = {skill.metadata.name for skill in skill_catalog}
        if decision.skill is not None and decision.skill not in skill_names:
            raise DecisionAgentError(
                f"Vision Decision Agent selected unregistered skill: {decision.skill}"
            )
        return decision

    @staticmethod
    def _recoverable_skill_names(
        skill_catalog: Sequence[RobotSkill[SkillArgs]],
    ) -> set[str]:
        recoverable: set[str] = set()
        for skill in skill_catalog:
            tags = set(skill.metadata.tags)
            schema = skill.args_model.model_json_schema()
            required = schema.get("required", [])
            if (
                "dangerous" not in tags
                and "operator_only" not in tags
                and (not isinstance(required, list) or not required)
            ):
                recoverable.add(skill.metadata.name)
        return recoverable

    @staticmethod
    def _parse_output(
        output: object,
        *,
        recoverable_skills: set[str] | None = None,
    ) -> AgentDecision:
        if isinstance(output, Mapping):
            candidate = output.get("structured_response", output)
            return AgentDecision.model_validate(
                _sanitize_visual_noop_payload(candidate)
            )
        if not isinstance(output, str):
            raise DecisionAgentError("Vision Decision Agent returned invalid output")
        text = output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else text
            if text.startswith("json"):
                text = text[4:].lstrip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                recovered = _recover_safe_noop(text)
                if recovered is not None:
                    return recovered
                recovered_skill = _recover_truncated_skill_decision(
                    text,
                    recoverable_skills or set(),
                )
                if recovered_skill is not None:
                    return recovered_skill
                raise DecisionAgentError(
                    "Vision Decision Agent did not return a JSON object; "
                    f"raw={text[:500]!r}"
                )
            try:
                decoded = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                recovered = _recover_safe_noop(text)
                if recovered is not None:
                    return recovered
                recovered_skill = _recover_truncated_skill_decision(
                    text,
                    recoverable_skills or set(),
                )
                if recovered_skill is not None:
                    return recovered_skill
                raise DecisionAgentError(
                    "Vision Decision Agent returned invalid JSON: "
                    f"{exc}; raw={text[:500]!r}"
                ) from exc
        return AgentDecision.model_validate(_sanitize_visual_noop_payload(decoded))


@dataclass(frozen=True, slots=True)
class VisionPolicyOutcome:
    decided_at_s: float
    frame_count: int
    window_start_s: float | None
    window_end_s: float | None
    decision: AgentDecision
    robot_state: RobotState
    executed: bool = False
    skill_result: SkillResult | None = None
    speech_spoken: bool = False
    suppressed_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        decision_age_s = (
            max(0.0, self.decided_at_s - self.window_end_s)
            if self.window_end_s is not None
            else None
        )
        return {
            "decided_at_s": self.decided_at_s,
            "frame_count": self.frame_count,
            "window_start_s": self.window_start_s,
            "window_end_s": self.window_end_s,
            "decision_age_s": decision_age_s,
            "decision": self.decision.to_dict(),
            "robot_state": {
                "hardware": self.robot_state.hardware,
                "connected": self.robot_state.connected,
                "details": self.robot_state.details,
            },
            "executed": self.executed,
            "skill_result": (
                self.skill_result.to_dict() if self.skill_result is not None else None
            ),
            "speech_spoken": self.speech_spoken,
            "suppressed_reason": self.suppressed_reason,
        }


@dataclass(frozen=True, slots=True)
class VisionPolicyError:
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class VisionPolicyDecision:
    decided_at_s: float
    frame_count: int
    window_start_s: float
    window_end_s: float
    decision: AgentDecision
    robot_state: RobotState
    policy_context: Mapping[str, object] | None = None
    model_metrics: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decided_at_s": self.decided_at_s,
            "frame_count": self.frame_count,
            "window_start_s": self.window_start_s,
            "window_end_s": self.window_end_s,
            "decision_age_s": max(
                0.0,
                self.decided_at_s - self.window_end_s,
            ),
            "decision": self.decision.to_dict(),
            "robot_state": {
                "hardware": self.robot_state.hardware,
                "connected": self.robot_state.connected,
                "details": self.robot_state.details,
            },
            "policy_context": dict(self.policy_context or {}),
            "model_metrics": dict(self.model_metrics or {}),
        }


class VisionPolicyWorker:
    def __init__(
        self,
        runtime: SkillRuntime,
        decision_agent: VisionDecisionAgent,
        video_buffer: VideoBuffer,
        *,
        speech: SpeechOutput | None = None,
        interval_s: float = 0.5,
        frame_count: int = 1,
        action_cooldown_s: float = 5.0,
        max_decision_age_s: float | None = None,
        queue_size: int = 16,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("vision policy interval must be greater than zero")
        if frame_count <= 0:
            raise ValueError("vision frame count must be greater than zero")
        if action_cooldown_s < 0:
            raise ValueError("action cooldown must not be negative")
        if max_decision_age_s is not None and max_decision_age_s <= 0:
            raise ValueError("maximum decision age must be greater than zero")
        self.runtime = runtime
        self.decision_agent = decision_agent
        self.video_buffer = video_buffer
        self.speech = speech
        self.interval_s = interval_s
        self.frame_count = frame_count
        self.action_cooldown_s = action_cooldown_s
        self.max_decision_age_s = max_decision_age_s
        self._decision_queue: asyncio.Queue[
            tuple[AgentDecision, tuple[CameraFrame, ...], RobotState]
        ] = asyncio.Queue(maxsize=1)
        self._outcome_queue: asyncio.Queue[VisionPolicyOutcome] = asyncio.Queue(
            maxsize=queue_size
        )
        self._policy_decision_queue: asyncio.Queue[VisionPolicyDecision] = (
            asyncio.Queue(maxsize=queue_size)
        )
        self._error_queue: asyncio.Queue[VisionPolicyError] = asyncio.Queue(
            maxsize=queue_size
        )
        self._worker_tasks: tuple[asyncio.Task[None], ...] = ()
        self._active_task: asyncio.Task[tuple[SkillResult | None, bool]] | None = None
        self._active_signature: str | None = None
        self._active_skill: str | None = None
        self._active_required_resources: tuple[str, ...] = ()
        self._last_selected_skill: str | None = None
        self._last_selected_at_s: float | None = None
        self._last_close_obstacle_at_s: float | None = None
        self._last_action_at: dict[str, float] = {}
        self._interrupt_lock = asyncio.Lock()
        self._safety_latched = False

    @property
    def running(self) -> bool:
        return bool(self._worker_tasks)

    @property
    def active_behavior(self) -> str | None:
        return self._active_signature

    @property
    def safety_latched(self) -> bool:
        return self._safety_latched

    def set_safety_latched(self, latched: bool) -> None:
        self._safety_latched = latched

    def observe_frame(self, frame: CameraFrame) -> None:
        distance_m = frame.nearest_obstacle_distance_m
        if (
            distance_m is not None
            and distance_m <= _HANDSHAKE_CONFIRMATION_DISTANCE_M
        ):
            self._last_close_obstacle_at_s = frame.observed_at_s

    async def start(self) -> None:
        if self.running:
            return
        self._worker_tasks = (
            asyncio.create_task(self._policy_loop(), name="vision-policy-worker"),
            asyncio.create_task(self._execution_loop(), name="vision-execution-worker"),
        )

    async def stop(self) -> None:
        tasks = self._worker_tasks
        self._worker_tasks = ()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        active = self._active_task
        if active is not None and not active.done():
            active.cancel()
            await asyncio.gather(active, return_exceptions=True)
        self._active_task = None
        self._active_signature = None
        self._active_skill = None
        self._active_required_resources = ()

    def drain_outcomes(self) -> tuple[VisionPolicyOutcome, ...]:
        return self._drain(self._outcome_queue)

    def drain_policy_decisions(self) -> tuple[VisionPolicyDecision, ...]:
        return self._drain(self._policy_decision_queue)

    def drain_errors(self) -> tuple[VisionPolicyError, ...]:
        return self._drain(self._error_queue)

    async def interrupt(
        self,
        reason: str = "interrupt requested",
        *,
        force_stop: bool = False,
    ) -> bool:
        async with self._interrupt_lock:
            active = self._active_task
            had_active_behavior = active is not None and not active.done()
            if had_active_behavior:
                active.cancel()
                await asyncio.gather(active, return_exceptions=True)
            self._active_task = None
            self._active_signature = None
            self._active_skill = None
            self._active_required_resources = ()
            if had_active_behavior or force_stop:
                try:
                    await self.runtime.robot.stop()
                except Exception as exc:  # noqa: BLE001 - report adapter failures upstream
                    self._put_latest(
                        self._error_queue,
                        VisionPolicyError(
                            stage="interrupt",
                            message=f"{reason}: {exc}",
                        ),
                    )
            return had_active_behavior

    async def stop_locomotion_for_safety(
        self,
        reason: str = "depth safety stop",
    ) -> bool:
        """Stop the mobile base without cancelling an upper-body-only action."""

        async with self._interrupt_lock:
            active = self._active_task
            had_active_locomotion = (
                active is not None
                and not active.done()
                and "mobile_base" in self._active_required_resources
            )
            if had_active_locomotion:
                active.cancel()
                await asyncio.gather(active, return_exceptions=True)
                self._active_task = None
                self._active_signature = None
                self._active_skill = None
                self._active_required_resources = ()
            try:
                await self.runtime.robot.stop()
            except Exception as exc:  # noqa: BLE001 - report adapter failures upstream
                self._put_latest(
                    self._error_queue,
                    VisionPolicyError(
                        stage="interrupt",
                        message=f"{reason}: {exc}",
                    ),
                )
            return had_active_locomotion

    async def _policy_loop(self) -> None:
        while True:
            started = time.monotonic()
            frames = self.video_buffer.sample(self.frame_count)
            if frames:
                try:
                    robot_state = await self.runtime.robot.get_state()
                    policy_context = self._build_policy_context()
                    decision = await self.decision_agent.decide(
                        frames,
                        robot_state,
                        self.runtime.registry.list(),
                        policy_context=policy_context,
                    )
                    decided_at_s = time.monotonic()
                    self._put_latest(
                        self._policy_decision_queue,
                        VisionPolicyDecision(
                            decided_at_s=decided_at_s,
                            frame_count=len(frames),
                            window_start_s=frames[0].observed_at_s,
                            window_end_s=frames[-1].observed_at_s,
                            decision=decision,
                            robot_state=robot_state,
                            policy_context=policy_context,
                            model_metrics=self.decision_agent.last_metrics,
                        ),
                    )
                    decision_age_s = max(
                        0.0,
                        decided_at_s - frames[-1].observed_at_s,
                    )
                    if (
                        self.max_decision_age_s is not None
                        and decision.action
                        in {"execute_skill", "execute_and_speak", "speak"}
                        and decision_age_s > self.max_decision_age_s
                        and not self._stale_handshake_has_fresh_confirmation(
                            decision,
                            decided_at_s=decided_at_s,
                        )
                    ):
                        self._put_latest(
                            self._outcome_queue,
                            self._outcome(
                                decision,
                                frames,
                                robot_state,
                                suppressed_reason=(
                                    "stale visual decision: "
                                    f"{decision_age_s:.2f}s old exceeds "
                                    f"{self.max_decision_age_s:.2f}s limit"
                                ),
                            ),
                        )
                    elif decision.action == "interrupt":
                        interrupted = await self.interrupt("vision policy")
                        self._put_latest(
                            self._outcome_queue,
                            self._outcome(
                                decision,
                                frames,
                                robot_state,
                                executed=interrupted,
                                suppressed_reason=(
                                    None if interrupted else "no active behavior"
                                ),
                            ),
                        )
                    else:
                        self._put_latest(
                            self._decision_queue,
                            (decision, frames, robot_state),
                        )
                except Exception as exc:  # noqa: BLE001 - policy must remain alive
                    self._put_latest(
                        self._error_queue,
                        VisionPolicyError(stage="decision", message=str(exc)),
                    )
            remaining = self.interval_s - (time.monotonic() - started)
            if remaining > 0:
                await asyncio.sleep(remaining)

    async def _execution_loop(self) -> None:
        while True:
            decision, frames, robot_state = await self._decision_queue.get()
            try:
                if decision.action in {"continue", "ignore"}:
                    self._put_latest(
                        self._outcome_queue,
                        self._outcome(decision, frames, robot_state),
                    )
                    continue

                if (
                    self._safety_latched
                    and decision.action in {"execute_skill", "execute_and_speak"}
                    and self._decision_uses_mobile_base(decision)
                    and decision.skill not in {"stop", "stop_move"}
                ):
                    self._put_latest(
                        self._outcome_queue,
                        self._outcome(
                            decision,
                            frames,
                            robot_state,
                            suppressed_reason=(
                                "depth safety latch blocks mobile-base skills"
                            ),
                        ),
                    )
                    continue

                if self._recovered_handshake_lacks_recent_proximity(decision):
                    self._put_latest(
                        self._outcome_queue,
                        self._outcome(
                            decision,
                            frames,
                            robot_state,
                            suppressed_reason=(
                                "recovered handshake lacks recent close-range "
                                "depth evidence"
                            ),
                        ),
                    )
                    continue

                signature = self._decision_signature(decision)
                now = time.monotonic()
                if self._active_signature == signature:
                    self._put_latest(
                        self._outcome_queue,
                        self._outcome(
                            decision,
                            frames,
                            robot_state,
                            suppressed_reason="identical behavior is already active",
                        ),
                    )
                    continue
                last_action_at = self._last_action_at.get(signature)
                if (
                    last_action_at is not None
                    and now - last_action_at < self.action_cooldown_s
                ):
                    self._put_latest(
                        self._outcome_queue,
                        self._outcome(
                            decision,
                            frames,
                            robot_state,
                            suppressed_reason="identical behavior is in cooldown",
                        ),
                    )
                    continue
                if self._active_task is not None and not self._active_task.done():
                    await self.interrupt("switching vision behavior")

                self._active_signature = signature
                self._active_skill = decision.skill
                self._active_required_resources = self._decision_required_resources(
                    decision
                )
                if decision.skill is not None:
                    self._last_selected_skill = self._canonical_skill_name(
                        decision.skill
                    )
                    self._last_selected_at_s = now
                self._last_action_at[signature] = now
                self._active_task = asyncio.create_task(
                    self._execute(decision),
                    name="vision-active-behavior",
                )
                try:
                    skill_result, speech_spoken = await self._active_task
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    continue
                finally:
                    self._active_task = None
                    self._active_signature = None
                    self._active_skill = None
                    self._active_required_resources = ()
                self._put_latest(
                    self._outcome_queue,
                    self._outcome(
                        decision,
                        frames,
                        robot_state,
                        executed=True,
                        skill_result=skill_result,
                        speech_spoken=speech_spoken,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - execution worker must survive
                self._active_task = None
                self._active_signature = None
                self._active_skill = None
                self._active_required_resources = ()
                self._put_latest(
                    self._error_queue,
                    VisionPolicyError(stage="execution", message=str(exc)),
                )

    async def _execute(self, decision: AgentDecision) -> tuple[SkillResult | None, bool]:
        skill_result: SkillResult | None = None
        if decision.action in {"execute_skill", "execute_and_speak"}:
            if decision.skill is None:
                raise RuntimeError("validated vision decision is missing a skill")
            skill_result = await self.runtime.execute(
                decision.skill,
                **decision.arguments,
            )
        speech_spoken = False
        if decision.action in {"speak", "execute_and_speak"}:
            if decision.speech is None:
                raise RuntimeError("validated vision decision is missing speech")
            if self.speech is not None:
                await self.speech.speak(decision.speech)
                speech_spoken = True
        return skill_result, speech_spoken

    def _decision_required_resources(
        self,
        decision: AgentDecision,
    ) -> tuple[str, ...]:
        if decision.skill is None:
            return ()
        try:
            return self.runtime.registry.get(
                decision.skill
            ).metadata.required_resources
        except KeyError:
            return ()

    def _decision_uses_mobile_base(self, decision: AgentDecision) -> bool:
        return "mobile_base" in self._decision_required_resources(decision)

    def _build_policy_context(self) -> dict[str, object]:
        context: dict[str, object] = {
            "active_skill": self._active_skill,
            "last_selected_skill": self._last_selected_skill,
            "safety_latched": self._safety_latched,
        }
        if self._last_selected_at_s is not None:
            context["seconds_since_last_selection"] = round(
                max(0.0, time.monotonic() - self._last_selected_at_s),
                3,
            )
        if self._last_close_obstacle_at_s is not None:
            context["seconds_since_close_obstacle"] = round(
                max(0.0, time.monotonic() - self._last_close_obstacle_at_s),
                3,
            )
        return context

    def _recovered_handshake_lacks_recent_proximity(
        self,
        decision: AgentDecision,
    ) -> bool:
        if (
            self._canonical_skill_name(decision.skill or "") != "handshake"
            or decision.reason != "recovered truncated model JSON"
        ):
            return False
        return not self._has_recent_close_obstacle(
            now_s=time.monotonic(),
            max_age_s=_RECOVERED_HANDSHAKE_CONFIRMATION_MAX_AGE_S,
        )

    def _stale_handshake_has_fresh_confirmation(
        self,
        decision: AgentDecision,
        *,
        decided_at_s: float,
    ) -> bool:
        if self._canonical_skill_name(decision.skill or "") != "handshake":
            return False
        return self._has_recent_close_obstacle(
            now_s=decided_at_s,
            max_age_s=_HANDSHAKE_CONFIRMATION_MAX_AGE_S,
        )

    def _has_recent_close_obstacle(
        self,
        *,
        now_s: float,
        max_age_s: float,
    ) -> bool:
        if self._last_close_obstacle_at_s is None:
            return False
        age_s = max(0.0, now_s - self._last_close_obstacle_at_s)
        return age_s <= max_age_s

    @staticmethod
    def _canonical_skill_name(skill_name: str) -> str:
        return _CANONICAL_SKILL_NAMES.get(skill_name, skill_name)

    @staticmethod
    def _decision_signature(decision: AgentDecision) -> str:
        return json.dumps(
            {
                "action": decision.action,
                "skill": (
                    VisionPolicyWorker._canonical_skill_name(decision.skill)
                    if decision.skill is not None
                    else None
                ),
                "arguments": decision.arguments,
                "speech": decision.speech,
            },
            ensure_ascii=True,
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def _outcome(
        decision: AgentDecision,
        frames: Sequence[CameraFrame],
        robot_state: RobotState,
        *,
        executed: bool = False,
        skill_result: SkillResult | None = None,
        speech_spoken: bool = False,
        suppressed_reason: str | None = None,
    ) -> VisionPolicyOutcome:
        return VisionPolicyOutcome(
            decided_at_s=time.monotonic(),
            frame_count=len(frames),
            window_start_s=(frames[0].observed_at_s if frames else None),
            window_end_s=(frames[-1].observed_at_s if frames else None),
            decision=decision,
            robot_state=robot_state,
            executed=executed,
            skill_result=skill_result,
            speech_spoken=speech_spoken,
            suppressed_reason=suppressed_reason,
        )

    @staticmethod
    def _put_latest[ItemT](queue: asyncio.Queue[ItemT], item: ItemT) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(item)

    @staticmethod
    def _drain[ItemT](queue: asyncio.Queue[ItemT]) -> tuple[ItemT, ...]:
        items: list[ItemT] = []
        while True:
            try:
                items.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                return tuple(items)

"""Verify the visual recipient before responding to social gestures."""
import json
import time
from collections.abc import Sequence

from .remote_vision import RemoteVisionInvoker
from .vision_policy import VisionDecisionAgent

VISUAL_CHECKS = (
    '\nDecision checks: The camera wearer is the robot. A person facing the camera '
    'and moving their raised hand is greeting this robot: wave back. A hand offered '
    'below shoulder height towards the camera is a handshake invitation. If two '
    'visible people greet or shake hands WITH EACH OTHER, ignore. Do not infer that '
    'a greeting is for you just because it is visible. Use continue ONLY if runtime '
    'context explicitly reports an action currently running. If idle with no request, '
    'use ignore. Follow the current task and output one action JSON.'
)
RECIPIENT_PROMPT = (
    "Who is the intended recipient of the greeting gesture? Look at the person's "
    'gaze, body orientation and hand direction. Answer exactly one: CAMERA '
    '(greeting the camera wearer), OTHER (greeting another person or someone off '
    'to the side), NONE (no greeting).'
)
SOCIAL_SKILLS = {'wave', 'wave_hand', 'handshake', 'shake_hand', 'high_five'}


class VerifiedSocialVisionInvoker(RemoteVisionInvoker):
    """For autonomous social observation; explicit tasks use RemoteVisionInvoker.

    All tools remain exposed. Only visually triggered social gestures require an
    independent recipient check; other skills retain normal runtime validation.
    """

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        started = time.monotonic()
        output = await super().ainvoke(frames, prompt + VISUAL_CHECKS)
        original_output = output
        first_metrics = dict(self.last_metrics)
        decision = VisionDecisionAgent._parse_output(output)
        verification = None
        verification_metrics = None
        if decision.skill in SOCIAL_SKILLS:
            verification = await super().ainvoke(frames, RECIPIENT_PROMPT)
            verification_metrics = dict(self.last_metrics)
            if verification.strip().upper() != 'CAMERA':
                output = json.dumps({'action': 'ignore'})
        self.last_metrics = {
            **first_metrics,
            'round_trip_s': round(time.monotonic() - started, 3),
            'recipient_verification': verification,
            'decision_raw': str(original_output),
            'verification_metrics': verification_metrics,
        }
        return output

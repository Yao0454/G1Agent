"""Separate visual gesture/recipient evidence from the full tool decision."""

import json
import re
import time
from collections.abc import Sequence

from .remote_vision import RemoteVisionInvoker

GESTURE_PROMPT = (
    'These images are a chronological video from your own head-mounted camera. '
    'Select what is happening:\n'
    'A. Someone waves hello to the camera wearer.\n'
    'B. Someone offers or performs a handshake with the camera wearer.\n'
    'C. People are greeting or shaking hands with each other, not the camera wearer.\n'
    'D. Someone is using a phone or computer, or there is no social interaction.\n'
    'E. Someone offers a high five to the camera wearer.\n'
    'Answer with just one letter: A, B, C, D, or E.'
)
RECIPIENT_PROMPT = (
    "Who is the intended recipient of the greeting gesture? Look at the person's "
    'gaze, body orientation and hand direction. Answer exactly one: CAMERA '
    '(greeting the camera wearer), OTHER (greeting another person or someone off '
    'to the side), NONE (no greeting).'
)
_GESTURES = {'A': 'wave', 'B': 'handshake', 'E': 'high_five'}


def is_visual_social_goal(goal: str) -> bool:
    """Conservatively enrich observation/response tasks, not direct commands.

    This selects an input augmentation, never tool availability. Unrecognized
    wording retains the ordinary visual decision path with all tools available.
    """
    social = re.search(r'挥手|握手|击掌|互动|打招呼|社交|\b(wav\w*|handshake|high.five|greet\w*|social gesture\w*)\b', goal, re.I)
    conditional = re.search(r'看到|看见|观察|识别|检测|回应|响应|\b(observe|watch|respond|react|detect|when|if)\b', goal, re.I)
    return bool(social and conditional)


class GroundedVisionInvoker(RemoteVisionInvoker):
    """Supply visual evidence without removing tools or overriding user goals.

    The final decision still uses the original images, task, history and complete
    catalog. Intermediate outputs are closed labels, never executable actions.
    """

    def __init__(self, *args, grounding_enabled: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.grounding_enabled = grounding_enabled

    async def ainvoke(self, frames: Sequence[object], prompt: str) -> object:
        self.last_prompt = prompt
        if not self.grounding_enabled:
            return await super().ainvoke(frames, prompt)
        started = time.monotonic()
        stages = []
        self.last_metrics = {}
        try:
            gesture = await super().ainvoke(frames, GESTURE_PROMPT)
            stages.append({'stage': 'gesture', **self.last_metrics})
            recipient = 'NONE'
            if gesture.strip() in _GESTURES:
                recipient = await super().ainvoke(frames, RECIPIENT_PROMPT)
                stages.append({'stage': 'recipient', **self.last_metrics})
            evidence = {
                'camera_directed_gesture': (
                    _GESTURES.get(gesture.strip(), 'none')
                    if recipient.strip() == 'CAMERA' else 'none'
                )
            }
            extra = (
                '\nAuxiliary visual observation (may be wrong): '
                + json.dumps(evidence)
                + '. Use this together with the images. For a goal of responding '
                'to gestures, match camera_directed_gesture to its registered tool; '
                'none means no gesture addressed to the robot, so ignore. Explicit '
                'user commands and non-social tasks still follow the original goal. '
                'Return the required action JSON.'
            )
            self.last_prompt = prompt + extra
            output = await super().ainvoke(frames, self.last_prompt)
            stages.append({'stage': 'decision', **self.last_metrics})
            self.last_metrics = {
                **self.last_metrics,
                'observation': evidence,
                'gesture_raw': gesture,
                'recipient_raw': recipient,
            }
            return output
        finally:
            self.last_metrics = {
                **self.last_metrics,
                'round_trip_s': round(time.monotonic() - started, 3),
                'stages': stages,
            }

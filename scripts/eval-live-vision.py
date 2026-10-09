"""Capture real camera windows and record visual decisions without moving hardware."""
import argparse
import asyncio
import hashlib
import io
import json
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from agent.remote_vision import RemoteVisionInvoker
from agent.vision_policy import VisionDecisionAgent
from core.runtime import SkillRuntime
from perception import CameraFrame, PerceptionResult
from robot import SimulatedRobotAdapter
from skills import register_g1_skills

GOAL = (
    '持续观察真实画面，只回应朝向机器人的明确互动。看到挥手时挥手回应；'
    '看到伸手请求握手时握手；看到明确请求击掌时击掌。'
    '无人、无明确互动或无法判断时等待。不要仅因有人出现就执行动作。'
    '同一次互动已回应后不要重复。'
)


class RecordingInvoker(RemoteVisionInvoker):
    async def ainvoke(self, frames, prompt):
        self.raw = None
        self.prompt = prompt
        self.raw = await super().ainvoke(frames, prompt)
        return self.raw


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--robot-url', default='http://192.168.31.198:8000')
    parser.add_argument('--windows', type=int, default=6)
    args = parser.parse_args()
    if args.windows < 1:
        parser.error('--windows must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'conditions.json').write_text(json.dumps({
        'goal': GOAL, 'robot_url': args.robot_url, 'frames_per_window': 8,
        'execution': 'simulation only', 'labels': 'not annotated; no accuracy score',
    }, ensure_ascii=False, indent=2))
    robot = SimulatedRobotAdapter()
    runtime = SkillRuntime(robot)
    register_g1_skills(runtime)
    invoker = RecordingInvoker()
    agent = VisionDecisionAgent(invoker=invoker, goal=GOAL, timeout_s=90)
    previous_version = None
    try:
        await agent.warmup()
        async with httpx.AsyncClient(base_url=args.robot_url, trust_env=False, timeout=10) as client:
            for index in range(args.windows):
                folder = args.output/f'window-{index+1:03d}'
                folder.mkdir()
                frames, metadata = [], []
                deadline = time.monotonic()+20
                while len(frames) < 8:
                    if time.monotonic() > deadline:
                        raise RuntimeError('Camera did not supply 8 distinct frame versions in 20 seconds')
                    response = await client.get('/api/v1/camera/frame.jpg')
                    response.raise_for_status()
                    version = response.headers.get('X-Frame-Version')
                    if version is None:
                        raise RuntimeError('Camera frame has no freshness version')
                    if version != previous_version:
                        data = response.content
                        with Image.open(io.BytesIO(data)) as im:
                            im.verify()
                        now = time.monotonic()
                        filename = f'frame-{len(frames):02d}.jpg'
                        (folder/filename).write_bytes(data)
                        frames.append(CameraFrame(now, data, None, PerceptionResult(now)))
                        metadata.append(dict(file=filename, version=version, received_at_s=now,
                                             sha256=hashlib.sha256(data).hexdigest()))
                        previous_version = version
                    await asyncio.sleep(0.25)
                (folder/'frames.json').write_text(json.dumps(metadata, indent=2))
                sheet = Image.new('RGB', (1280, 520))
                draw = ImageDraw.Draw(sheet)
                for j, frame in enumerate(frames):
                    with Image.open(io.BytesIO(frame.rgb)) as im:
                        im.thumbnail((320,240))
                        x,y = (j%4)*320,(j//4)*260
                        sheet.paste(im,(x,y))
                        draw.text((x+4,y+240), str(j),fill='white')
                sheet.save(folder/'contact-sheet.jpg')
                row = {'window': index+1, 'ground_truth': None}
                try:
                    decision = await agent.decide(frames, await robot.get_state(), runtime.registry.list())
                    row['decision'] = decision.model_dump()
                    if decision.skill:
                        result = await runtime.execute(decision.skill, **decision.arguments)
                        row['simulated_result'] = result.to_dict()
                        if result.success:
                            agent.record_action(decision)
                except Exception as exc:
                    row['error'] = str(exc)
                row.update(raw=invoker.raw, metrics=agent.last_metrics)
                (folder/'result.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
                (folder/'prompt.txt').write_text(invoker.prompt)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        await agent.close()


if __name__ == '__main__':
    asyncio.run(main())

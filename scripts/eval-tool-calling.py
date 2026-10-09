"""Evaluate the real remote model with production prompts and simulated execution."""
import argparse
import asyncio
import io
import json
import statistics
import time
from pathlib import Path

from PIL import Image
from agent.remote_vision import RemoteVisionInvoker
from agent.vision_policy import VisionDecisionAgent
from core.runtime import SkillRuntime
from perception import CameraFrame, PerceptionResult
from robot import SimulatedRobotAdapter
from skills import register_g1_skills


class RecordingInvoker(RemoteVisionInvoker):
    async def ainvoke(self, frames, prompt):
        self.raw = None
        self.prompt = prompt
        self.raw = await super().ainvoke(frames, prompt)
        return self.raw


def cases_for(runtime):
    required = {
        'handshake': {'duration_s': 1}, 'shake_hand': {'duration_s': 1},
        'continuous_gait': {'enabled': False}, 'switch_move_mode': {'enabled': False},
        'set_speed_mode': {'mode': 1}, 'set_fsm_id': {'fsm_id': 500},
        'set_balance_mode': {'balance_mode': 0}, 'set_swing_height': {'swing_height': 0.1},
        'set_stand_height': {'stand_height': 0.7},
        'set_velocity': {'vx': 0.1, 'vy': -0.1, 'omega': 0.2},
        'move_sdk': {'vx': 0.1, 'vy': 0, 'vyaw': -0.2},
        'set_task_id': {'task_id': 0}, 'switch_to_internal_ctrl': {'mode': 'last'},
        'fsm_api': {'parameter': '{}'},
        'execute_custom_arm_action': {'action_name': 'test-action'},
    }
    cases = []
    for skill in runtime.registry.list():
        name = skill.metadata.name
        args = required.get(name, {})
        skill.args_model.model_validate(args)
        cases.append(dict(id='explicit_'+name, group='explicit',
            goal=f'现在调用工具 {name} 一次，参数为 {json.dumps(args, ensure_ascii=False)}。使用指定工具名称，未指定参数使用默认值。',
            skills=[name], arguments=args))
    natural = [
        ('鼓掌一次。', ['clap'], {}),
        ('用右手挥手打个招呼。', ['wave', 'wave_hand'], {'arm':'right'}),
        ('向前走二十厘米。', ['move_forward'], {'distance_m':0.2}),
        ('向后退十厘米。', ['move_backward'], {'distance_m':0.1}),
        ('向左平移十五厘米。', ['move_left'], {'distance_m':0.15}),
        ('向右平移三十厘米。', ['move_right'], {'distance_m':0.3}),
        ('向左转三十度。', ['turn_left'], {'angle_deg':30}),
        ('向右转四十五度。', ['turn_right'], {'angle_deg':45}),
        ('停止移动。', ['stop', 'stop_move'], {}),
        ('把速度模式设置成整数 2。', ['set_speed_mode'], {'mode':2}),
        ('关闭连续步态。', ['continuous_gait'], {'enabled':False}),
        ('将摆腿高度设为 0.12 米。', ['set_swing_height'], {'swing_height':0.12}),
        ('切换回上一次的内部控制模式。', ['switch_to_internal_ctrl'], {'mode':'last'}),
        ('设置前向速度为 0.1，侧向速度为 -0.1，角速度为 0.2，使用 set_velocity。', ['set_velocity'], {'vx':0.1,'vy':-0.1,'omega':0.2}),
    ]
    for i, (goal, names, args) in enumerate(natural):
        runtime.registry.get(names[0]).args_model.model_validate(args)
        cases.append(dict(id=f'natural_{i+1:02}', group='natural', goal=goal, skills=names, arguments=args))
    for i, goal in enumerate([
        '现在没有任何任务，请保持等待，不执行动作。',
        '只有看到有人向镜头挥手时才挥手回应，否则不执行任何动作。',
        '只在画面中明确看到有人伸手请求握手时才握手，否则等待。',
        '鼓掌任务已经成功完成一次，现在不要重复，保持等待。',
    ]):
        cases.append(dict(id=f'noop_{i+1:02}', group='noop', goal=goal, actions=['ignore']))
    return cases


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    robot = SimulatedRobotAdapter()
    runtime = SkillRuntime(robot)
    register_g1_skills(runtime)
    cases = cases_for(runtime)
    (args.output/'cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2)+'\n')
    buffer = io.BytesIO()
    Image.new('RGB', (640,480), (128,128,128)).save(buffer, format='JPEG')
    jpeg = buffer.getvalue()
    (args.output/'input.jpg').write_bytes(jpeg)
    invoker = RecordingInvoker()
    rows = []
    await invoker.warmup()
    try:
        with (args.output/'results.jsonl').open('w') as output:
            for case in cases:
                agent = VisionDecisionAgent(invoker=invoker, goal=case['goal'], timeout_s=90)
                now = time.monotonic()
                frames = [CameraFrame(now, jpeg, None, PerceptionResult(now))]
                row = dict(case=case, strict_json=False, schema_valid=False, correct=False)
                started = time.monotonic()
                try:
                    decision = await agent.decide(frames, await robot.get_state(), runtime.registry.list())
                    row['decision'] = decision.model_dump()
                    if decision.skill:
                        skill = runtime.registry.get(decision.skill)
                        parsed = skill.args_model.model_validate(decision.arguments).model_dump()
                        row['schema_valid'] = True
                        row['correct'] = decision.action in ('execute_skill','execute_and_speak') and decision.skill in case.get('skills',[]) and all(parsed.get(k)==v for k,v in case.get('arguments',{}).items())
                        result = await runtime.execute(decision.skill, **decision.arguments)
                        row['simulated_result'] = result.to_dict()
                    else:
                        row['schema_valid'] = True
                        row['correct'] = decision.action in case.get('actions',[])
                except Exception as exc:
                    row['error'] = str(exc)
                try:
                    raw = json.loads(invoker.raw)
                    row['strict_json'] = isinstance(raw, dict) and (
                        set(raw) == {'decision', 'state_update'} or
                        ('action' in raw and set(raw) <= {'action', 'skill', 'arguments', 'speech'})
                    )
                except (ValueError, TypeError):
                    pass
                row.update(raw=invoker.raw, metrics=invoker.last_metrics, elapsed_s=round(time.monotonic()-started,3))
                (args.output/(case['id']+'.prompt.txt')).write_text(invoker.prompt)
                output.write(json.dumps(row, ensure_ascii=False, default=str)+'\n')
                output.flush()
                rows.append(row)
                print(f"{len(rows)}/{len(cases)} {case['id']} correct={row['correct']} {row.get('decision',row.get('error'))}", flush=True)
    finally:
        await invoker.close()
    summary = dict(total=len(rows), correct=sum(r['correct'] for r in rows), strict_json=sum(r['strict_json'] for r in rows), schema_valid=sum(r['schema_valid'] for r in rows), errors=sum('error' in r for r in rows), simulated_success=sum(r.get('simulated_result',{}).get('success',False) for r in rows), median_round_trip_s=statistics.median(r['metrics'].get('round_trip_s',r['elapsed_s']) for r in rows), groups={g:dict(total=sum(r['case']['group']==g for r in rows),correct=sum(r['correct'] for r in rows if r['case']['group']==g)) for g in ('explicit','natural','noop')}, limitation='One fixed gray image; real remote inference, simulated execution. Not a visual-recognition or real-hardware benchmark.')
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())

"""Public video evaluation: labels and filenames never enter model prompts."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import statistics
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw
from agent.vision_policy import VisionDecisionAgent
from agent.grounded_vision import GroundedVisionInvoker
from perception import CameraFrame, PerceptionResult
from core.runtime import SkillRuntime
from robot import SimulatedRobotAdapter
from skills import register_g1_skills

spec = importlib.util.spec_from_file_location('live_eval', Path(__file__).with_name('eval-live-vision.py'))
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def prepare(root):
    root.mkdir(parents=True, exist_ok=False)
    cases = []
    for category in ('handwaving', 'walking', 'handclapping', 'empty'):
        source_category = 'walking' if category == 'empty' else category
        video = Path('evaluations/public-datasets')/f'kth-{source_category}.avi'
        duration = float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]))['format']['duration'])
        for fraction in (.2,.5,.8):
            start = round((duration-2)*fraction, 2)
            if category == 'walking':
                start = {0.2: 0.5, 0.5: 10.0, 0.8: 18.0}[fraction]
            name = f'{category}-{int(fraction*100)}'
            folder = root/name
            folder.mkdir()
            subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(video),'-t','2','-vf','fps=4','-frames:v','8',str(folder/'frame-%02d.jpg')],check=True)
            frames=sorted(folder.glob('frame-*.jpg'))
            assert len(frames)==8
            sheet=Image.new('RGB',(640,280))
            draw=ImageDraw.Draw(sheet)
            for i,path in enumerate(frames):
                with Image.open(path) as im:
                    im.thumbnail((160,120)); x,y=i%4*160,i//4*140
                    sheet.paste(im,(x,y));draw.text((x+4,y+120),f'{start+i*.25:.2f}s',fill='white')
            sheet.save(folder/'contact-sheet.jpg')
            cases.append(dict(id=name,category=category,start_s=start,expected_skills=['wave','wave_hand'] if category=='handwaving' else [],expected_actions=[] if category=='handwaving' else ['ignore'],video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),source=f'https://www.csc.kth.se/cvap/actions/person15_{source_category}_d1_uncomp.avi'))
    (root/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))


class RecordingGroundedInvoker(GroundedVisionInvoker):
    async def ainvoke(self, frames, prompt):
        self.raw = None
        self.prompt = prompt
        self.raw = await super().ainvoke(frames, prompt)
        self.prompt = self.last_prompt
        return self.raw


async def evaluate(root, grounded=False):
    cases=json.loads((root/'cases.json').read_text())
    invoker=RecordingGroundedInvoker() if grounded else live.RecordingInvoker()
    (root/'run.json').write_text(json.dumps({'invoker': type(invoker).__name__, 'goal': live.GOAL, 'model': invoker.model_name, 'execution': 'simulation only'}, ensure_ascii=False, indent=2))
    rows=[]
    await invoker.warmup()
    try:
        for case in cases:
            folder=root/case['id']
            # Each window is an independent trial. No ground truth is sent to the model.
            robot=SimulatedRobotAdapter();runtime=SkillRuntime(robot);register_g1_skills(runtime)
            agent=VisionDecisionAgent(invoker=invoker,goal=live.GOAL,timeout_s=90)
            now=time.monotonic()
            frames=[CameraFrame(now+i*.25,p.read_bytes(),None,PerceptionResult(now+i*.25)) for i,p in enumerate(sorted(folder.glob('frame-*.jpg')))]
            row=dict(case=case,correct=False)
            try:
                decision=await agent.decide(frames,await robot.get_state(),runtime.registry.list())
                row['decision']=decision.model_dump()
                row['correct']=decision.action in case['expected_actions'] or (decision.action=='execute_skill' and decision.skill in case['expected_skills'])
                if decision.skill:
                    result=await runtime.execute(decision.skill,**decision.arguments)
                    row['simulated_result']=result.to_dict()
                    row['correct']=row['correct'] and result.success
            except Exception as exc:row['error']=str(exc)
            row.update(raw=invoker.raw,metrics=agent.last_metrics)
            (folder/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
            (folder/'prompt.txt').write_text(invoker.prompt)
            rows.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
    finally:await agent.close()
    summary=dict(total=len(rows),correct=sum(r['correct'] for r in rows),errors=sum('error' in r for r in rows),median_s=statistics.median(r['metrics'].get('round_trip_s',0) for r in rows),groups={c:dict(total=sum(r['case']['category']==c for r in rows),correct=sum(r['correct'] for r in rows if r['case']['category']==c)) for c in sorted({case['category'] for case in cases})})
    (root/'summary.json').write_text(json.dumps(summary,indent=2))
    print(summary)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','evaluate']);parser.add_argument('output',type=Path);parser.add_argument('--grounded',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':prepare(args.output)
    else:asyncio.run(evaluate(args.output, grounded=args.grounded))

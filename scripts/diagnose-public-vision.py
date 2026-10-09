"""Separate visual recognition probe; does not select or execute robot tools."""
import asyncio
import json
from pathlib import Path
from agent.remote_vision import RemoteVisionInvoker

PROMPT = ('Observe these ordered video frames. Classify the visible human motion. '
          'Return only JSON with one key action, choosing one of: waving, clapping, '
          'walking, standing, no_person, other. Do not choose a robot action.')

async def main():
    root=Path('evaluations/public-vision-kth-reviewed')
    invoker=RemoteVisionInvoker()
    rows=[]
    try:
        for case in json.loads((root/'cases.json').read_text()):
            frames=[p.read_bytes() for p in sorted((root/case['id']).glob('frame-*.jpg'))]
            row={'id':case['id'],'expected':{'handwaving':'waving','handclapping':'clapping','walking':'walking','empty':'no_person'}[case['category']]}
            try:
                raw=await invoker.ainvoke(frames,PROMPT)
                row.update(raw=raw,metrics=invoker.last_metrics)
                row['correct']=json.loads(raw).get('action')==row['expected']
            except Exception as exc:row.update(error=str(exc),correct=False)
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    finally:await invoker.close()
    (root/'recognition-probe.json').write_text(json.dumps({'prompt':PROMPT,'results':rows,'correct':sum(r['correct'] for r in rows),'total':len(rows)},ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main())

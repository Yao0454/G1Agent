"""Evaluate frozen observation labels through the real remote model API."""
import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from agent.remote_vision import RemoteVisionInvoker


async def main(args):
    rows=[json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    args.output.mkdir(parents=True,exist_ok=False)
    invoker=RemoteVisionInvoker(base_url=args.url,model_name=args.model,max_new_tokens=16)
    results=[]
    await invoker.warmup()
    try:
        with (args.output/'results.jsonl').open('w') as out:
            for row in rows:
                result={k:row[k] for k in ('id','video_id','source_sha256','task','answer','split')}
                try:
                    raw=await invoker.ainvoke([(args.dataset.parent/p).read_bytes() for p in row['images']],row['prompt'])
                    result.update(raw=raw,correct=raw.strip()==row['answer'],metrics=invoker.last_metrics)
                except Exception as exc:
                    result.update(error=str(exc),correct=False)
                results.append(result);out.write(json.dumps(result)+'\n');out.flush()
                print(row['id'],result['correct'],result.get('raw',result.get('error')),flush=True)
    finally:
        await invoker.close()
    groups=defaultdict(list)
    for row in results:groups[row['task']+':'+row['answer']].append(row['correct'])
    report={'total':len(results),'correct':sum(r['correct'] for r in results),
            'errors':sum('error' in r for r in results),
            'macro_accuracy':sum(sum(v)/len(v) for v in groups.values())/len(groups),
            'groups':{k:{'correct':sum(v),'total':len(v)} for k,v in groups.items()}}
    (args.output/'summary.json').write_text(json.dumps(report,indent=2));print(report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--url',default='http://192.168.31.143:8011')
    p.add_argument('--model',default='models/UnifoLM-ER-1')
    asyncio.run(main(p.parse_args()))

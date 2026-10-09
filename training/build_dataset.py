"""Export reviewed visual supervision and enforce video/hash split isolation."""
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from agent.grounded_vision import GESTURE_PROMPT, RECIPIENT_PROMPT


def build(root, output):
    manifest = json.loads((root/'manifest.json').read_text())
    annotations = json.loads((root/'annotations.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    seen = {}
    ids = set()
    rows = {'train': [], 'validation': [], 'test': []}
    excluded = []
    for clip in manifest:
        if clip['id'] in ids:
            raise ValueError('Duplicate clip ID: '+clip['id'])
        ids.add(clip['id'])
        split = clip['split']
        if split not in rows:
            raise ValueError('Invalid split')
        old_split = seen.setdefault(clip['source_sha256'], split)
        if old_split != split:
            raise ValueError('Video hash leakage: '+clip['id'])
        a = annotations.get(clip['id'])
        if not a or not a.get('reviewed') or a.get('exclude'):
            excluded.append(clip['id'])
            continue
        if a['gesture'] not in ('A','B','C','D','E') or a['recipient'] not in ('CAMERA','OTHER','NONE'):
            raise ValueError('Invalid annotation: '+clip['id'])
        if not a.get('note'):
            raise ValueError('Visual review note required: '+clip['id'])
        images = [(root/p).resolve() for p in clip['images']]
        if len(images)!=8 or any(not p.is_file() for p in images):
            raise ValueError('Missing image: '+clip['id'])
        for task, prompt, answer in [('gesture',GESTURE_PROMPT,a['gesture']),('recipient',RECIPIENT_PROMPT,a['recipient'])]:
            rows[split].append(dict(id=clip['id']+'/'+task, video_id=clip['id'],
                source_sha256=clip['source_sha256'], split=split, task=task,
                images=[os.path.relpath(p, output.resolve()) for p in images], prompt=prompt, answer=answer))
    if not all(rows.values()):
        raise ValueError('All three splits need reviewed examples')
    for split, examples in rows.items():
        (output/f'{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in examples))
    report = {'examples':{k:len(v) for k,v in rows.items()},'excluded':excluded,
              'classes':{k:dict(Counter(r['answer'] for r in v)) for k,v in rows.items()},
              'manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),
              'annotations_sha256':hashlib.sha256((root/'annotations.json').read_bytes()).hexdigest(),
              'limitation':'video-disjoint, not subject-disjoint; no high-five positives unless explicitly reviewed'}
    (output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();build(a.root,a.output)

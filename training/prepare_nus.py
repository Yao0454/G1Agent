"""Prepare auditable image windows; proposed labels require visual review."""
import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


def prepare(source, output):
    output.mkdir(parents=True, exist_ok=False)
    review_dir = output / 'review'
    review_dir.mkdir()
    rows = []
    for category_dir in sorted(source.iterdir()):
        videos = sorted(category_dir.glob('*.mp4')) if category_dir.is_dir() else []
        if not videos:
            continue
        category = category_dir.name
        fresh_test_ids = {p.stem for p in videos[-2:]}
        for video in videos:
            clip_id = f'{category}-{video.stem}'
            duration = float(json.loads(subprocess.check_output([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(video)
            ]))['format']['duration'])
            start = max(0, round(duration / 2 - 1, 2))
            window_s = min(2, duration - start)
            folder = output / 'frames' / clip_id
            folder.mkdir(parents=True)
            subprocess.run([
                'ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(video),
                '-vf', f'fps={8/window_s:.8f},scale=640:-2,tpad=stop_mode=clone:stop_duration=1',
                '-frames:v', '8', str(folder / '%02d.jpg'),
            ], check=True)
            frames = sorted(folder.glob('*.jpg'))
            if len(frames) != 8:
                raise ValueError(f'Expected 8 frames for {clip_id}')
            split = ('test' if video.stem in fresh_test_ids or int(video.stem) in (7,8,9)
                     else 'validation' if int(video.stem) in (4,5,6) else 'train')
            label = {'wave': 'A', 'shake': 'B', '3wave': 'C', '3shake': 'C'}.get(category, 'D')
            recipient = 'CAMERA' if category in ('wave', 'shake') else 'OTHER' if category in ('3wave', '3shake') else 'NONE'
            rows.append(dict(
                id=clip_id, source_video=str(video), category=category, split=split,
                source_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                start_s=start, duration_s=window_s,
                frame_offsets_s=[round(i*window_s/8,6) for i in range(8)],
                images=[str(p.relative_to(output)) for p in frames],
                proposed_gesture=label, proposed_recipient=recipient,
                reviewed=False, reviewer_note='',
            ))
    (output / 'manifest.json').write_text(json.dumps(rows, indent=2))
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['category'], row['split'])].append(row)
    for (category, split), samples in grouped.items():
        for page in range(0, len(samples), 5):
            chunk = samples[page:page+5]
            sheet = Image.new('RGB', (1280, len(chunk)*205), '#181818')
            draw = ImageDraw.Draw(sheet)
            for index, row in enumerate(chunk):
                y = index*205
                draw.text((5,y+2), f"{row['id']} [{split}] proposed {row['proposed_gesture']} / {row['proposed_recipient']}", fill='white')
                for frame_index, path in enumerate(row['images']):
                    with Image.open(output/path) as im:
                        im.thumbnail((160,180))
                        sheet.paste(im,(frame_index*160,y+25))
            sheet.save(review_dir/f'{category}-{split}-{page//5+1:02d}.jpg')
    (output / 'provenance.json').write_text(json.dumps({
        'source': 'https://sites.google.com/view/sanath-narayan/Datasets',
        'license': 'NUSFPID: academic purposes only',
        'label_status': 'proposed only; never train before review',
        'split': 'video-disjoint; not subject-disjoint; 07-09 and last two category IDs held out',
        'test_usage': '07-09 used previously for prompt evaluation, never for adapter fitting; last two IDs new',
        'samples':len(rows),
    },indent=2))
    print(json.dumps({s:sum(r['split']==s for r in rows) for s in ['train','validation','test']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('evaluations/public-datasets/NUSFPID'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    prepare(args.source,args.output)

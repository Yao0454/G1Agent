"""Prepare NUSFPID pilot windows for manual review before evaluation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--ids',type=int,nargs='+',required=True)
args=parser.parse_args()
root=args.output;root.mkdir(parents=True,exist_ok=False)
cases=[]
for category in ['wave','shake','3wave','3shake','cell','type']:
 for video in sorted((Path('evaluations/public-datasets/NUSFPID')/category).glob('*.mp4')):
  if int(video.stem) not in args.ids: continue
  duration=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]))['format']['duration'])
  start=max(0,round(duration/2-1,2));name=f'{category}-{video.stem}';folder=root/name;folder.mkdir()
  subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(video),'-vf',f'fps={8/min(2,duration-start):.8f},scale=640:-2,tpad=stop_mode=clone:stop_duration=1','-frames:v','8',str(folder/'frame-%02d.jpg')],check=True)
  frames=sorted(folder.glob('frame-*.jpg'));assert len(frames)==8
  sheet=Image.new('RGB',(1280,400));draw=ImageDraw.Draw(sheet)
  for i,p in enumerate(frames):
   with Image.open(p) as im:
    im.thumbnail((320,180));x,y=i%4*320,i//4*200;sheet.paste(im,(x,y));draw.text((x+4,y+180),f'{start+i*min(2,duration-start)/8:.2f}s',fill='white')
  sheet.save(folder/'contact-sheet.jpg')
  cases.append(dict(id=name,category=category,start_s=start,expected_skills={'wave':['wave','wave_hand'],'shake':['handshake','shake_hand']}.get(category,[]),expected_actions=[] if category in ['wave','shake'] else ['ignore'],video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),source='https://sites.google.com/view/sanath-narayan/Datasets'))
(root/'cases.json').write_text(json.dumps(cases,indent=2))
for category in ['wave','shake','3wave','3shake','cell','type']:
 paths=sorted(root.glob(category+'-*/contact-sheet.jpg'));im=Image.new('RGB',(1280,420*len(paths)));draw=ImageDraw.Draw(im)
 for i,p in enumerate(paths):
  with Image.open(p) as src:im.paste(src,(0,i*420+20))
  draw.text((0,i*420),p.parent.name,fill='white')
 im.save(root/(category+'-overview.jpg'))

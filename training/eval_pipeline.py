"""Run existing full-catalog visual eval against a candidate server endpoint."""
import argparse,asyncio,importlib.util
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--url',required=True)
a=p.parse_args()
spec=importlib.util.spec_from_file_location('public_eval',Path('scripts/eval-public-vision.py'))
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
Base=ev.RecordingGroundedInvoker
class Candidate(Base):
 def __init__(self):super().__init__(base_url=a.url)
ev.RecordingGroundedInvoker=Candidate
asyncio.run(ev.evaluate(a.output,grounded=True))

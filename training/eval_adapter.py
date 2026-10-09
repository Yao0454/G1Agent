"""Compare a selected observer adapter and base using identical preprocessing."""
import argparse,json
from pathlib import Path
import torch
from transformers import AutoProcessor,Qwen3VLForConditionalGeneration
from peft import PeftModel
from train_lora import load_rows,evaluate

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',required=True);p.add_argument('--adapter',required=True)
p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
processor=AutoProcessor.from_pretrained(a.adapter,extra_special_tokens={})
base=Qwen3VLForConditionalGeneration.from_pretrained(a.model,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':'cuda:0'})
model=PeftModel.from_pretrained(base,a.adapter).eval()
rows=load_rows(a.dataset)
for name,enabled in [('base',False),('adapter',True)]:
 if enabled:report=evaluate(model,processor,rows,'cuda:0')
 else:
  with model.disable_adapter():report=evaluate(model,processor,rows,'cuda:0')
 (a.output/(name+'.json')).write_text(json.dumps(report,indent=2))
 print(json.dumps({'variant':name,'accuracy':report['accuracy'],'macro_accuracy':report['macro_accuracy'],'groups':report['groups']}),flush=True)

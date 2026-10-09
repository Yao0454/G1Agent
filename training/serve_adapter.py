"""Serve a LoRA observer alongside unchanged base-model general decisions.

Wrap the existing server rather than replacing its queue and cancellation logic.
Only the exact two audited observation prompts use the adapter.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from contextlib import nullcontext

from peft import PeftModel
from transformers import AutoProcessor
import uvicorn

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--server-script',type=Path,required=True)
p.add_argument('--model',required=True);p.add_argument('--adapter',required=True)
p.add_argument('--prompts',type=Path,required=True)
p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8012)
a=p.parse_args()
spec=importlib.util.spec_from_file_location('base_server',a.server_script)
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
BaseRuntime=server.UnifolmRuntime
prompts=set(json.loads(a.prompts.read_text()))
assert len(prompts)==2


class ObserverRuntime(BaseRuntime):
    def __init__(self,model_path):
        super().__init__(model_path)
        self.model=PeftModel.from_pretrained(self.model,a.adapter).eval()
        self.base_processor=self.processor
        self.observer_processor=AutoProcessor.from_pretrained(a.adapter,extra_special_tokens={})

    def invoke(self,body):
        # Existing server's asyncio lock serializes the entire invocation.
        observer=body.prompt in prompts
        self.processor=self.observer_processor if observer else self.base_processor
        try:
            with nullcontext() if observer else self.model.disable_adapter():
                result=super().invoke(body)
            result['metrics']['observer_adapter']=str(Path(a.adapter).resolve()) if observer else None
            return result
        finally:
            self.processor=self.base_processor


server.UnifolmRuntime=ObserverRuntime
uvicorn.run(server.create_app(a.model),host=a.host,port=a.port,log_level='info')

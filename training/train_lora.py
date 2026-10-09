"""Train a Qwen3-VL visual-observer adapter; never merge/overwrite base weights.

Uses eight images exactly as the observation API does. Only assistant answer
and end-of-turn tokens contribute to the loss. Test data is never loaded here.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path


def load_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty dataset')
    for row in rows:
        row['images'] = [str((path.parent / p).resolve()) for p in row['images']]
    return rows


def validate_splits(train, validation):
    for key in ('video_id', 'source_sha256'):
        if {r[key] for r in train} & {r[key] for r in validation}:
            raise ValueError('Training/validation leakage: '+key)
    for row in train+validation:
        if row['task'] not in ('gesture','recipient') or len(row['images']) != 8:
            raise ValueError('Unexpected observation sample')
        allowed = ('A','B','C','D','E') if row['task']=='gesture' else ('CAMERA','OTHER','NONE')
        if row['answer'] not in allowed:
            raise ValueError('Invalid target')


def prepare_adapter(model, rank):
    from peft import LoraConfig, get_peft_model
    config = LoraConfig(r=rank, lora_alpha=2*rank, lora_dropout=.05, bias='none',
        target_modules=r'.*language_model.*\.(q_proj|k_proj|v_proj|o_proj)$', task_type='CAUSAL_LM')
    model = get_peft_model(model, config)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    trainable = [(n,p) for n,p in model.named_parameters() if p.requires_grad]
    if not trainable or any('lora_' not in n or 'language_model' not in n for n,_ in trainable):
        raise RuntimeError('Unexpected trainable weights')
    return model, trainable


def answer_loss(model, inputs, count):
    import torch.nn.functional as F
    if not 0 < count < inputs['input_ids'].shape[1]:
        raise ValueError('Invalid answer length')
    # Keep only the causal positions that predict the assistant answer.
    logits = model(**inputs, use_cache=False, logits_to_keep=count+1).logits
    labels = inputs['input_ids'][:,-count:]
    return F.cross_entropy(logits[:,:-1,:].float().reshape(-1,logits.shape[-1]),labels.reshape(-1))


def encode(processor, row, device, with_answer=True):
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    import torch
    images = []
    for path in row['images']:
        with Image.open(path) as image:
            images.append(image.convert('RGB'))
    messages = [{'role':'user','content':[
        *[{'type':'image','image':im} for im in images], {'type':'text','text':row['prompt']}
    ]}]
    images, _ = process_vision_info(messages)
    prefix = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    prefix_inputs = processor(text=[prefix], images=images, return_tensors='pt')
    prefix_len = prefix_inputs['input_ids'].shape[1]
    if not with_answer:
        return {k:v.to(device) for k,v in prefix_inputs.items()}, 0
    messages.append({'role':'assistant','content':[{'type':'text','text':row['answer']}]})
    full_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    inputs = processor(text=[full_text], images=images, return_tensors='pt')
    if not torch.equal(inputs['input_ids'][0,:prefix_len],prefix_inputs['input_ids'][0]):
        raise ValueError('Chat template prefix mismatch; refusing to supervise user/image tokens')
    target_count = inputs['input_ids'].shape[1]-prefix_len
    if not 1 <= target_count <= 16:
        raise ValueError(f'Unexpected answer token count: {target_count}')
    return {k:v.to(device) for k,v in inputs.items()}, target_count


def evaluate(model, processor, rows, device):
    import torch
    from collections import defaultdict
    groups=defaultdict(list);predictions=[]
    model.eval()
    with torch.no_grad():
        for row in rows:
            inputs,_=encode(processor,row,device,False)
            generated=model.generate(**inputs,max_new_tokens=8,do_sample=False)
            raw=processor.tokenizer.decode(generated[0,inputs['input_ids'].shape[1]:],skip_special_tokens=True).strip()
            correct=raw==row['answer'];groups[(row['task'],row['answer'])].append(correct)
            predictions.append(dict(id=row['id'],expected=row['answer'],raw=raw,correct=correct))
    return {'accuracy':sum(r['correct'] for r in predictions)/len(predictions),
            'macro_accuracy':sum(sum(v)/len(v) for v in groups.values())/len(groups),
            'groups':{':'.join(k):{'correct':sum(v),'total':len(v)} for k,v in groups.items()},
            'predictions':predictions}


def main(args):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA training host required; no job was started')
    train=load_rows(args.train);validation=load_rows(args.validation)
    validate_splits(train,validation)
    args.output.mkdir(parents=True,exist_ok=False)
    random.seed(args.seed);torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    processor=AutoProcessor.from_pretrained(args.model, extra_special_tokens={})
    # Fixed resizing must also be used for adapter inference, stored in run.json.
    processor.image_processor.size={'shortest_edge':65536,'longest_edge':args.max_pixels}
    model=Qwen3VLForConditionalGeneration.from_pretrained(
        args.model,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':'cuda:0'})
    model, trainable = prepare_adapter(model, args.rank)
    run=vars(args).copy();run={k:str(v) if isinstance(v,Path) else v for k,v in run.items()}
    run.update(train_sha256=hashlib.sha256(args.train.read_bytes()).hexdigest(),
        validation_sha256=hashlib.sha256(args.validation.read_bytes()).hexdigest(),
        trainable_parameters=sum(p.numel() for _,p in trainable),torch_version=torch.__version__,
        gpu=torch.cuda.get_device_name(0),status='running')
    (args.output/'run.json').write_text(json.dumps(run,indent=2))
    optimizer=torch.optim.AdamW([p for _,p in trainable],lr=args.lr,weight_decay=.01)
    best=-1.;step=0
    total_steps=math.ceil(len(train)/args.accumulation)*args.epochs
    for epoch in range(args.epochs):
        random.shuffle(train);model.train();optimizer.zero_grad(set_to_none=True)
        loss_sum=0.
        for index,row in enumerate(train):
            inputs,count=encode(processor,row,'cuda:0')
            # Avoid materializing 153k-vocabulary logits for thousands of image/prompt tokens.
            loss=answer_loss(model,inputs,count)
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite training loss')
            group_size=min(args.accumulation,len(train)-(index//args.accumulation)*args.accumulation)
            (loss/group_size).backward();loss_sum+=loss.item()
            if (index+1)%args.accumulation==0 or index+1==len(train):
                torch.nn.utils.clip_grad_norm_([p for _,p in trainable],1.)
                step+=1;warmup=max(1,int(total_steps*.05))
                factor=min(step/warmup,1.)*max(.1,(total_steps-step)/max(1,total_steps-warmup))
                for group in optimizer.param_groups:group['lr']=args.lr*factor
                optimizer.step();optimizer.zero_grad(set_to_none=True)
                print(json.dumps({'epoch':epoch+1,'step':step,'loss':loss.item(),'gpu_peak_gb':torch.cuda.max_memory_allocated()/1e9}),flush=True)
        metrics=evaluate(model,processor,validation,'cuda:0')
        metrics['train_loss']=loss_sum/len(train)
        (args.output/f'validation-epoch-{epoch+1}.json').write_text(json.dumps(metrics,indent=2))
        checkpoint=args.output/f'epoch-{epoch+1}';model.save_pretrained(checkpoint);processor.save_pretrained(checkpoint)
        if metrics['macro_accuracy']>best:
            best=metrics['macro_accuracy'];run['best_checkpoint']=str(checkpoint);run['best_validation_macro_accuracy']=best
        (args.output/'run.json').write_text(json.dumps(run,indent=2))
        print(json.dumps({'epoch':epoch+1,'validation_macro_accuracy':metrics['macro_accuracy']}),flush=True)
    run['status']='completed';(args.output/'run.json').write_text(json.dumps(run,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--train',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rank',type=int,default=8);p.add_argument('--epochs',type=int,default=3)
    p.add_argument('--accumulation',type=int,default=8);p.add_argument('--lr',type=float,default=5e-5)
    p.add_argument('--seed',type=int,default=20261009);p.add_argument('--max-pixels',type=int,default=262144)
    a=p.parse_args()
    if min(a.rank,a.epochs,a.accumulation)<=0 or a.lr<=0 or a.max_pixels<65536:p.error('Invalid training hyperparameters')
    main(a)

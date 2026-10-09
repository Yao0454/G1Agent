"""CPU implementation check using real processor + random tiny Qwen3-VL.

This never trains the user's actual model and never measures its accuracy.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import torch
from transformers import AutoProcessor, Qwen3VLConfig, Qwen3VLForConditionalGeneration
from peft import PeftModel
from train_lora import answer_loss, encode, load_rows, prepare_adapter


def digest(parameters):
    result=hashlib.sha256()
    for name, parameter in parameters:
        result.update(name.encode());result.update(parameter.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return result.hexdigest()


def main(args):
    torch.manual_seed(2718);torch.set_num_threads(2)
    processor=AutoProcessor.from_pretrained(args.processor,local_files_only=True)
    processor.image_processor.size={'shortest_edge':65536,'longest_edge':262144}
    config=Qwen3VLConfig.from_pretrained(args.processor,local_files_only=True)
    text=config.text_config
    text.hidden_size=64;text.intermediate_size=128;text.num_hidden_layers=2
    text.num_attention_heads=4;text.num_key_value_heads=2;text.head_dim=16
    text.rope_parameters['mrope_section']=[2,3,3]
    vision=config.vision_config
    vision.depth=2;vision.hidden_size=32;vision.intermediate_size=64
    vision.num_heads=4;vision.out_hidden_size=64;vision.deepstack_visual_indexes=[0]
    config.hidden_size=64
    model,trainable=prepare_adapter(Qwen3VLForConditionalGeneration(config),2)
    model.train()
    row=load_rows(args.dataset)[0]
    inputs,count=encode(processor,row,'cpu')
    base=[(n,p) for n,p in model.named_parameters() if not p.requires_grad]
    base_before=digest(base);adapter_before=digest(trainable)
    optimizer=torch.optim.AdamW([p for _,p in trainable],lr=1e-3)
    loss=answer_loss(model,inputs,count)
    assert torch.isfinite(loss), 'nonfinite loss'
    loss.backward()
    grads=[p.grad for _,p in trainable if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads), 'nonfinite/missing gradients'
    assert any(torch.count_nonzero(g) for g in grads), 'all gradients zero'
    assert all(p.grad is None for _,p in base), 'base weights received gradients'
    optimizer.step()
    assert digest(base)==base_before, 'base weights changed'
    assert digest(trainable)!=adapter_before, 'adapter weights did not change'
    model.eval()
    with torch.no_grad():
        # Full-logit reference proves truncated loss masks only answer tokens.
        logits=model(**inputs,use_cache=False).logits
        labels=inputs['input_ids'].clone()
        labels[:,:-count]=-100
        reference=torch.nn.functional.cross_entropy(logits[:,:-1].float().reshape(-1,logits.shape[-1]),labels[:,1:].reshape(-1))
        actual=answer_loss(model,inputs,count)
        torch.testing.assert_close(reference,actual)
        prompt,_=encode(processor,row,'cpu',False)
        generated=model.generate(**prompt,max_new_tokens=2,do_sample=False)
        assert generated.shape[1]>prompt['input_ids'].shape[1]
    with tempfile.TemporaryDirectory() as directory:
        model.save_pretrained(directory)
        assert (Path(directory)/'adapter_model.safetensors').is_file()
        fresh=Qwen3VLForConditionalGeneration(config)
        loaded=PeftModel.from_pretrained(fresh,directory)
        saved={n:p for n,p in model.named_parameters() if 'lora_' in n}
        for name,param in loaded.named_parameters():
            if name in saved:torch.testing.assert_close(param,saved[name])
    report={'kind':'tiny random CPU implementation check, not model fine-tuning',
        'loss':loss.item(),'input_tokens':inputs['input_ids'].shape[1],'answer_tokens':count,
        'image_grid':inputs['image_grid_thw'].tolist(),'trainable_parameters':sum(p.numel() for _,p in trainable),
        'finite_gradients':True,'adapter_changed':True,'base_unchanged':True,
        'masked_loss_matches_full_reference':True,'checkpoint_roundtrip':True,
        'generation_works':True,'torch':torch.__version__}
    args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--processor',required=True);p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())

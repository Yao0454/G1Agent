# UnifoLM-ER-1 visual fine-tuning

Status: model-host access was supplied and CUDA LoRA training is running on
`yaoyifeng@192.168.31.143`, directory `/home/yaoyifeng/g1-visual-training`.
Actual host: RTX 3080 20GB, torch 2.14.0+cu130, transformers 5.17.0,
PEFT 0.21.2. The training environment imports existing inference packages
read-only through a .pth file and installs PEFT separately; live packages were
not upgraded. The existing `go2-unifolm-server.service` is temporarily stopped
to release GPU memory. Base weights are retained at
`/home/yaoyifeng/Go2Agent/models/UnifoLM-ER-1`.
Training uses qwen-vl-utils preprocessing, matching the existing server.
Checkpoint selection and independent evaluation remain in progress; do not
claim training is finished or accuracy improved until the reports are complete.

## Current artifacts

- `evaluations/finetuning/nus-v1`: 286 videos, eight chronological JPEGs per video, manifests and contact sheets. Proposed split: 158 train / 48 validation / 80 test videos. A video and all its questions stay in one split.
- `annotations.json`: Codex visually reviewed 99 clips from wave/shake/3wave/3shake/3cell/3type. Seven ambiguous/cropped clips excluded. These are visual model annotations, not independently verified human labels.
- `evaluations/finetuning/nus-reviewed-v1`: 90 training / 34 validation / 60 test questions from 45/17/30 reviewed videos. Each video yields a gesture question and a recipient question. Relative image paths survive transfer to another machine.
- `evaluations/finetuning/baseline-validation-v1`: real inference baseline 21/34 exact answers, zero API errors, macro accuracy 0.6476. D 6/6, C 1/5, B 3/3, A 2/3; NONE 0/6, OTHER 5/5, CAMERA 4/6. These are observer answers, **not end-to-end robot action accuracy**.
- `train_lora.py`: Qwen3VL conditional generation + PEFT, bf16, rank-8 language-attention LoRA, frozen vision encoder and base weights, answer-only next-token loss, gradient accumulation/checkpointing, per-epoch validation and adapter checkpoints. No merging/overwriting base weights. CUDA execution and processor/template compatibility remain unverified pending host access.

### Verified implementation smoke check

`smoke_lora.py` uses the public Unitree processor/tokenizer and a tiny, randomly initialized Qwen3-VL on CPU. The same `prepare_adapter`, `encode` and `answer_loss` functions are used by the trainer. It passed forward/backward, finite nonzero gradients, adapter weight change, unchanged frozen base, equality with a full-logit masked loss reference, generation, and adapter save/reload. Evidence: `evaluations/finetuning/cpu-implementation-smoke.json`. Eight actual images produced 1,891 input tokens and three supervised answer tokens. This **does not** verify 4B GPU memory/runtime, improve the deployed model, or establish accuracy gains.

The isolated test environment is `/tmp/g1-lora-check-env`; its exact versions are recorded in `cpu-smoke-requirements.txt`. This is a macOS CPU test environment, not a CUDA dependency prescription. The live app environment was not upgraded.

```sh
/tmp/g1-lora-check-env/bin/python training/smoke_lora.py \
  --processor /tmp/g1-unifolm-processor \
  --dataset evaluations/finetuning/nus-reviewed-v1/train.jsonl \
  --output evaluations/finetuning/cpu-implementation-smoke.json
```

## Run after host inspection

First inspect the actual model config/revision, server preprocessing/chat template, CUDA device/memory, occupied GPUs, installed torch/transformers/PEFT, and existing jobs. Public Unitree model config says Qwen3VLForConditionalGeneration, 4B, transformers 5.5.3; do not assume the running local copy is identical.

Use an isolated training environment compatible with the actual CUDA installation. Expected libraries: torch, transformers supporting Qwen3VL and `logits_to_keep`, peft, accelerate, pillow. Do not upgrade the live inference environment just to train.

```sh
PYTHONPATH=src .venv/bin/python training/build_dataset.py \
  evaluations/finetuning/nus-v1 evaluations/finetuning/new-export

# On the CUDA host after transferring the data and verifying a one-step smoke run:
python training/train_lora.py \
  --model /actual/path/to/UnifoLM-ER-1 \
  --train evaluations/finetuning/nus-reviewed-v1/train.jsonl \
  --validation evaluations/finetuning/nus-reviewed-v1/validation.jsonl \
  --output training-runs/nus-lora-v1 --epochs 3
```

The trainer refuses an existing output directory and refuses cross-split video/hash leakage. It never loads the test file. Validate a forward/backward and verify trainable LoRA weights actually change before launching the full run. Adapter checkpoint selection uses validation macro accuracy, not the test results.

## Remaining work before completion

1. Obtain model-host SSH access and inspect resources/preprocessing. Match train and inference image handling.
2. Verify the trainer with actual model and one-step weight change, including finite gradients, answer token mask, memory and runtime. Improve/repair based on evidence.
3. Run training to completion; retain log, immutable base identity, config, checkpoint hashes and validation results.
4. Load the selected adapter and compare against base on the frozen test split, separating never-used last-two clips from 07–09 previously used for prompt testing. Report per-class recall, recipient confusion, invalid outputs and latency.
5. Evaluate real vision-to-tool behavior with the full tool catalog. No global action improvement claim from observer-only scores. Recheck direct tool commands and parameters.
6. Serve the adapter for visual observations only, while final general tool decisions retain base weights unless full regressions prove otherwise. Deploy only a demonstrated improvement, preserve rollback, and smoke-test real robot camera with simulated actuation.

## Limitations

NUSFPID is academic-only. Splits are video-disjoint but **not person-disjoint**, so this is a pilot and subject/scene leakage remains possible. Data has no high-five positive videos: don't claim improved high-five recognition. C denotes other people greeting, D denotes no greeting, not all forms of interaction. Some B windows show handshake contact/end rather than invitation; training these observation labels does not solve action-phase gating. Excluded samples are recorded before adapter evaluation rather than removed after inspecting its failures.

Need to expand or independently audit labels and keep real-camera generalization separate from public-video scores. Do not count this preparation, unit tests, or prompt changes as completed fine-tuning.

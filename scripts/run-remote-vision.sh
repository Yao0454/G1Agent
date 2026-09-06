#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"
exec .venv/bin/python -m app.perception \
  --vision-backend ollama --model qwen2.5vl:3b \
  --ollama-url http://127.0.0.1:11435 \
  --vision-task social --video-window-s 0.8 --vision-frame-count 3 \
  --vision-json-mode prompt --vision-max-new-tokens 160 --no-audio "$@"

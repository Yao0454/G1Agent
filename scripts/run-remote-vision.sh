#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec .venv/bin/python -m app.perception \
  --vision-backend remote --model models/UnifoLM-ER-1 \
  --vision-url http://192.168.31.143:8011 \
  --vision-task general --video-window-s 2 --vision-frame-count 8 \
  --vision-rotation-deg 180 --vision-max-new-tokens 256 "$@"

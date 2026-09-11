#!/usr/bin/env bash
set -euo pipefail
cd /root/ComfyUI
if pgrep -f 'main.py.*8188' >/dev/null; then
  exit 0
fi
nohup /root/miniconda3/bin/python main.py --listen 0.0.0.0 --port 8188 --use-sage-attention > /root/comfyui.log 2>&1 < /dev/null &

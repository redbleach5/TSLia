#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:-../models/qwen2.5-7b-instruct-q4_k_m.gguf}"
PORT="${LIYA_LLM_PORT:-8080}"
if [[ ! -f "$MODEL" ]]; then
  echo "Model not found: $MODEL" >&2
  echo "Download a GGUF model into /home/user/liya/models/." >&2
  exit 1
fi
llama-server -m "$MODEL" --host 127.0.0.1 --port "$PORT"
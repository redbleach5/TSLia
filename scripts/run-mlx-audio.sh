#!/usr/bin/env bash
set -euo pipefail

HOST="${MLX_AUDIO_HOST:-127.0.0.1}"
PORT="${MLX_AUDIO_PORT:-8000}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "MLX-Audio runner is intended for Apple Silicon macOS." >&2
  exit 2
fi

if ! command -v mlx_audio.server >/dev/null 2>&1; then
  echo "mlx_audio.server not found. Install MLX-Audio in the active Python environment first." >&2
  exit 1
fi

exec mlx_audio.server --host "$HOST" --port "$PORT"

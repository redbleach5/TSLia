#!/usr/bin/env bash
set -euo pipefail
printf 'OS: '; uname -a
python3 --version
if command -v ffmpeg >/dev/null; then ffmpeg -version | head -n 1; else echo 'ffmpeg: not installed'; fi
if command -v llama-server >/dev/null; then echo 'llama-server: installed'; else echo 'llama-server: not installed'; fi
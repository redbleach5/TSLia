# Запуск на macOS

## Подготовка

```bash
git clone https://github.com/redbleach5/TSLia.git
cd TSLia
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config.example.json config.json
```

## LLM через MLX-LM

Установите MLX-LM согласно инструкции MLX и запустите сервер:

```bash
mlx_lm.server --model mlx-community/Qwen3-8B-Instruct-4bit --port 8080
```

Для M1 Max с 64 ГБ можно начать с 8B/4-bit, затем сравнить 14B или 20–32B по задержке и качеству. Оставляйте запас памяти для STT, TTS и macOS.

## STT

Нужен сервер с OpenAI-совместимым endpoint `POST /v1/audio/transcriptions`. Подойти может адаптер над whisper.cpp или MLX-Audio Whisper.

## TTS

Baseline: Piper. Для эксперимента с более естественным голосом — MLX-Audio/Kokoro. Русские голоса необходимо проверить отдельно.

## Проверка

```bash
liya doctor
liya chat
```

## Следующие шаги

Нативный macOS-клиент должен добавить разрешение микрофона, AVAudioEngine, VAD, push-to-talk и воспроизведение TTS-буферов.
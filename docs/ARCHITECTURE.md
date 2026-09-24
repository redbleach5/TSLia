# Архитектура Лии

```text
Microphone / WAV
       ↓
STT endpoint :8081
       ↓
Dialogue orchestrator
       ├── persona
       ├── JSONL conversation memory
       └── local LLM endpoint :8080
       ↓
TTS endpoint :8082
       ↓
Speaker / output/liya.wav
```

## Backend contract

Приложение не зависит от конкретной реализации моделей. Оно обращается к локальным OpenAI-совместим HTTP API.

- LLM: `POST /v1/chat/completions`;
- STT: `POST /v1/audio/transcriptions` с multipart-полем `file`;
- TTS: `POST /v1/audio/speech` с JSON-полями `input`, `voice`, `model`.

## Mac profile

- LLM: MLX-LM;
- STT: Whisper или MLX-Audio Whisper;
- TTS: Piper baseline, затем Kokoro/MLX-Audio;
- audio: нативный macOS-клиент в следующих версиях.

## WSL profile

- LLM: llama.cpp server с GGUF;
- STT: whisper.cpp-совместимый сервис;
- TTS: Piper-совместимый сервис;
- хранилище и кэш Linux FS.

## Принципы

- аудио не отправляется в облако по умолчанию;
- конфигурация и секреты не коммитятся;
- опасные инструменты требуют подтверждения;
- backend-agnostic код должен одинаково работать на macOS и WSL.
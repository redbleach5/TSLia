# Архитектура Лии

## Целевая схема

```text
Микрофон / WAV
      ↓
Tauri + AudioWorklet
      ↓ PCM16, mono, 32 kHz
WebSocket transport
      ↓
TurnManager + VAD
      ↓
STT backend
  ├── LocalHttpSTT (batch)
  └── MacSpeechAnalyzerSTT (native bridge, Mac)
      ↓ final/interim transcript
Dialogue Runtime
  ├── turn_id / reply_id / generation
  ├── persona
  ├── facts memory
  └── local LLM SSE
      ↓
SentenceBuffer
      ↓
TTS backend
  ├── batch WAV
  └── future streaming TTS
      ↓
ordered Web Audio playback
      ↓
AnalyserNode + VRM lip sync
```

## Что реализовано сейчас

- PCM transport в браузере реализован через `AudioWorklet`.
- WebSocket runtime группирует PCM и создаёт WAV для batch STT.
- `server.py` содержит turn lifecycle, generation guard и отмену активных задач.
- `LocalClients` обращается к локальным HTTP endpoints и имеет configurable timeout.
- `select_stt()` выбирает `LocalHttpSTT` или `StreamingSTTBackend` по capability.
- `MacSpeechAnalyzerSTT` — контракт будущего Swift bridge; без bridge используется fallback.
- LLM использует OpenAI-compatible SSE.
- TTS phrases синтезируются параллельно, но отправляются в исходном порядке.
- Frontend использует `AudioBufferSourceNode`, а не замену `<audio>.src`.
- VRM обновляется через `vrm.update()` и получает аудио для базового lip sync.
- SQLite хранит только явно извлечённые факты с дедупликацией.

## Transport и capability policy

| Слой | Текущий режим | Не следует называть |
|---|---|---|
| Микрофон → runtime | live PCM chunks | live STT |
| HTTP STT | batch upload | streaming STT |
| HTTP LLM | SSE stream | multimodal voice stream |
| HTTP TTS | batch WAV | streaming TTS |
| Frontend playback | ordered Web Audio | streaming synthesis |

`stt_backend` в конфигурации:

```text
local_http     — текущий batch HTTP backend
macos_speech   — native SpeechAnalyzer bridge, fallback на local_http
```

`stt_stream` включается только реальным incremental backend, а не наличием ключа `stream` в HTTP payload.

## Turn lifecycle

Каждый turn получает:

```text
turn_id
reply_id
generation
cancel_event
```

При новом turn старые STT/LLM/TTS/preemptive результаты не должны отправляться в UI. Кнопка остановки отменяет активные asyncio tasks, но blocking HTTP request внутри `to_thread` может завершиться позже — это ограничение требует отдельного cancellable transport.

## Memory policy

Текущая память:

```text
SQLite facts
```

Извлекаются только явные фразы, например имя или предпочтение. Факты не считаются системными инструкциями. Перед добавлением RAG необходимо добавить trust boundary и prompt-injection tests.

## Security model

Сейчас Tauri имеет базовый CSP, но локальный WebSocket `ws://127.0.0.1:8765` пока не имеет session token/origin authentication. Это допустимо для локального прототипа, но не для MCP и destructive tools.

Перед инструментами нужны:

- capability-scoped commands;
- read/write split;
- explicit confirmation;
- audit log;
- no arbitrary shell;
- session nonce;
- strict local origin checks.

## Platform profiles

### macOS

- LLM: MLX-LM;
- STT: native SpeechAnalyzer target или локальный Whisper batch;
- TTS: Piper baseline, затем MLX-Audio/Kokoro;
- audio: Tauri AudioWorklet сейчас, native Swift bridge next.

### Windows/WSL

- LLM: llama.cpp/GGUF или OpenAI-compatible local server;
- STT: whisper.cpp/faster-whisper compatible HTTP;
- TTS: Piper compatible HTTP;
- UI: Tauri build where supported, browser dev server otherwise.

## Source of truth

Документация разделена на:

- [STATUS.md](STATUS.md) — что реально работает и что нет;
- [ROADMAP.md](ROADMAP.md) — последовательность следующих изменений;
- [MACOS.md](MACOS.md) — запуск и mac-specific constraints;
- [WSL.md](WSL.md) — переносимый Linux profile;
- [UI_RUNTIME.md](UI_RUNTIME.md) — capture/playback policy.

# Статус проекта

Версия документации соответствует commit `7a12b61` и текущему состоянию репозитория.

## Подтверждено

- Python CLI и локальные HTTP endpoints LLM/STT/TTS.
- Tauri 2 + React + TypeScript интерфейс с `Lia_v2.vrm`.
- Микрофонный PCM transport через `AudioWorklet` и локальный WebSocket.
- Локальная batch STT конфигурация по умолчанию.
- SSE streaming LLM, sentence buffer, parallel batch TTS и ordered Web Audio playback.
- Capability policy: локальный STT по умолчанию не объявляется streaming.
- Turn lifecycle: `turn_id`, `reply_id`, generation guard и единая отмена.
- Базовый SQLite facts memory с просмотром и удалением.
- 26 Python tests, React/Vite build и Tauri `cargo check` проходят.

## Не считается готовым

- Настоящий Mac `SpeechAnalyzer` bridge: контракт есть, Swift bridge отсутствует.
- Настоящий incremental STT: локальный HTTP backend batch; interim transcript не создаётся по умолчанию.
- Настоящий streaming TTS: текущий TTS возвращает WAV/chunked HTTP, но не синтезирует аудио по мере речи.
- Silero VAD и server-side endpointing в production-контуре.
- Barge-in во время речи: кнопка «Стоп» и turn cancellation есть, автоматическое распознавание перебития отсутствует.
- Полноценный wake word.
- RAG, MCP, опасные инструменты и подтверждения действий.
- Production-уровень безопасности локального WebSocket, Tauri capabilities и session auth.

## Важное различие

```text
PCM transport ≠ streaming STT
SSE LLM ≠ streaming TTS
Web Audio queue ≠ TTS synthesis streaming
preemptive draft ≠ гарантированно правильный ответ
```

Эти ограничения намеренно не скрываются за интерфейсом.

## Следующий рубеж

1. Собрать нативный SpeechAnalyzer bridge на Mac.
2. Перевести turn manager на явные `turn_id/generation` события во всех протоколах.
3. Реализовать incremental STT session с volatile/final transcript.
4. Подключить server-side VAD и endpointing.
5. Реализовать streaming TTS с backpressure и ordered playback.
6. После измерения latency включить wake word и barge-in.
7. Затем добавлять память документов, MCP и proactive behavior.

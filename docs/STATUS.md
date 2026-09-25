
# Статус проекта

Версия документации соответствует текущему состоянию репозитория. Проверяемые команды: `pytest -q`, `npm run build` и `cargo check`.

## Подтверждено

- Python CLI и локальные HTTP endpoints LLM/STT/TTS.
- Tauri 2 + React + TypeScript интерфейс с glTF-аватаром.
- Микрофонный PCM transport через `AudioWorklet` и локальный WebSocket.
- Локальная batch STT конфигурация по умолчанию.
- SSE streaming LLM, sentence buffer, parallel batch TTS и ordered Web Audio playback.
- Capability policy: локальный STT по умолчанию не объявляется streaming.
- Turn lifecycle: `turn_id`, `reply_id`, generation guard и единая отмена.
- Базовый SQLite facts memory с просмотром и удалением.
- Python, React/Vite и Tauri проверки проходят; фиксированное число тестов не используется как критерий готовности.
- Server-side endpointing по PCM (`VadSession`) и выбор VAD-backend: `vad_backend = "silero"` поднимает Silero ONNX (`silero_vad.py`), при отсутствии модели/`onnxruntime` или сбое инференса сессия прозрачно остаётся на энергетическом пороге.
- Скользящие latency-метрики p50/p95 по фазам stt/llm/tts/total (`latency.py`), событие `latency_stats` и бюджет `latency_p95_budget_ms` для отката рискованных оптимизаций.
- Выбор бэкенда мимики `face_backend`, health-probe Audio2Face-3D NIM и отчёт в `liya doctor`.
- Безопасный контракт кадра `face_frame` с нормализацией ARKit-52 и приоритетом внешнего кадра в UI-риге.

## Не считается готовым

- **Не считать готовым:** настоящий Mac `SpeechAnalyzer` bridge: контракт есть, Swift bridge отсутствует.
- **Профиль:** основной локальный runtime рассчитан на MacBook M1 Max с 64 ГБ unified memory; Audio2Face-3D NIM является только внешним NVIDIA-профилем и не работает на Apple GPU.
- Настоящий incremental STT: локальный HTTP backend batch; interim transcript не создаётся по умолчанию. Для M1 Max MLX-Audio Whisper (`whisper-large-v3-turbo`) и Apple Speech рассматриваются как отдельные кандидаты, но их streaming/on-device поведение и мост в проект ещё не измерены.
- Настоящий streaming TTS: текущий TTS возвращает WAV/chunked HTTP, но не синтезирует аудио по мере речи. MLX-Audio документирует CLI streaming и Kokoro/Chatterbox/Dia, однако это не означает готовый streaming HTTP backend Лии.
- Chatterbox имеет официальный macOS-пример выбора MPS; заявленные сторонние ускорения и экономия RAM не считаются подтверждёнными без benchmark на M1 Max.
- Silero VAD в production-контуре: backend выбирается через `vad_backend`, но модель `silero_vad.onnx` не поставляется с репозиторием, пороги не откалиброваны на реальном микрофоне и latency на целевом железе не измерена.
- Barge-in во время речи: кнопка «Стоп» и turn cancellation есть, автоматическое распознавание перебития отсутствует.
- Полноценный wake word.
- RAG, MCP, опасные инструменты и подтверждения действий.
- Production-уровень безопасности локального WebSocket, Tauri capabilities и session auth.
- Реальный Audio2Face-3D `ProcessAudioStream`: gRPC-транспорт, Web Audio replay-clock и измерения качества/латентности на NIM ещё не реализованы. Границы и план — [FACE.md](FACE.md).

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
4. Откалибровать пороги Silero VAD и снять p50/p95 latency на реальном железе (метрики уже собираются).
5. Реализовать streaming TTS с backpressure и ordered playback.
6. После измерения latency включить wake word и barge-in.
7. Затем добавлять память документов, MCP и proactive behavior.

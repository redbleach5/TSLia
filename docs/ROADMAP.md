# Дорожная карта Лии

Статус и ограничения текущей версии описаны в [STATUS.md](STATUS.md). Ниже roadmap отделён от экспериментального кода.

## Завершено: фундамент MVP

- [x] Python CLI и локальный HTTP-контур LLM/STT/TTS.
- [x] WebSocket runtime и Tauri desktop UI.
- [x] `Lia_v2.vrm` через Three.js и `@pixiv/three-vrm`.
- [x] PCM capture через `AudioWorklet`, mono PCM16, 32 kHz.
- [x] Web Audio playback queue и базовый lip sync.
- [x] SSE streaming LLM и sentence buffer.
- [x] Параллельная пакетная TTS-синтезация фраз с сохранением порядка.
- [x] Turn lifecycle и отмена активного ответа.
- [x] Capability policy и выбор batch/streaming STT.
- [x] Контракт `MacSpeechAnalyzerSTT` с fallback на `LocalHttpSTT`.
- [x] SQLite facts memory с просмотром и удалением.
- [x] 26 Python tests, React/Vite build, Tauri `cargo check`.

## Этап A — честный voice runtime

- [ ] Выделить `TurnManager` из `server.py`.
- [ ] Передавать `turn_id` и `generation` во все WebSocket events.
- [ ] Сделать server-side VAD с Silero ONNX.
- [ ] Разделить `final transcript`, `interim transcript` и `cancelled`.
- [ ] Не запускать preemptive draft для коротких/нестабильных interim.
- [ ] Проверить фактические PCM sample rate, frame size и временные метки.
- [ ] Добавить интеграционный тест PCM → WAV → fake batch STT → fake LLM → fake TTS.

## Этап B — Mac SpeechAnalyzer

- [ ] Создать Swift target/plugin в `ui/src-tauri` или отдельном macOS package.
- [ ] Реализовать разрешения микрофона и `SpeechAnalyzer`/`SpeechTranscriber`.
- [ ] Проверить загрузку on-device модели для `ru-RU`.
- [ ] Передавать volatile и finalized transcript через Tauri events.
- [ ] Подключить bridge к `MacSpeechAnalyzerSTT`.
- [ ] Проверить fallback, если модель не установлена или OS API недоступен.
- [ ] Измерить end-to-end latency на M1 Max.

## Этап C — streaming output

- [ ] Выбрать и подключить TTS backend с настоящим chunked output.
- [ ] Передавать sample rate и format metadata.
- [ ] Добавить backpressure и лимит незавершённых chunks.
- [ ] Сохранять ordered playback при разной скорости TTS workers.
- [ ] Добавить audio cancellation на границе chunk.
- [ ] Добавить phoneme/viseme mapping только после измерения качества.

## Этап D — естественный turn-taking

- [ ] Wake word через отдельный low-power loop.
- [ ] Автоматическое завершение речи по VAD/semantic endpoint.
- [ ] Barge-in через voice activity во время TTS.
- [ ] Echo cancellation и защита от самопереслушивания VRM/TTS.
- [ ] Инструмент отмены текущего LLM HTTP stream.
- [ ] Нагрузочные тесты 30–60 минут разговора.

## Этап E — память и личность

- [ ] Профиль пользователя с режимом явного подтверждения памяти.
- [ ] Session/fleeting/recent/permanent memory levels.
- [ ] SQLite FTS5 retrieval.
- [ ] Опциональный sqlite-vec после baseline retrieval.
- [ ] Импорт/экспорт и полное удаление памяти.
- [ ] Persona JSON: характер, настроение, уровень инициативы.
- [ ] Проверка prompt injection через факты и документы.

## Этап F — инструменты

- [ ] MCP client с capability discovery.
- [ ] Read-only инструменты первыми.
- [ ] Календарь, заметки и локальные файлы.
- [ ] Confirmation UI для write/destructive операций.
- [ ] Audit log и журнал отказов.
- [ ] Apple Shortcuts/HomeKit/Home Assistant adapter.
- [ ] Не выдавать tool call за выполненное действие без результата.

## Этап G — качество и релиз

- [ ] WER/CER на русском benchmark set.
- [ ] First-token, first-audio, total latency benchmarks.
- [ ] Memory/CPU/GPU profiles для 8B/14B/32B.
- [ ] Piper против Kokoro/MLX-Audio на русском.
- [ ] VRM expression capability detection.
- [ ] CSP, Tauri capabilities, WebSocket session token и origin checks.
- [ ] macOS notarization/signing и automated release.

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
- [x] 81 Python tests, React/Vite build, Tauri `cargo check`.

## Этап A — честный voice runtime

- [x] Выделить `TurnManager` из `server.py` — `turn.py`, `server.py` делегирует через свойства.
- [x] Передавать `turn_id` и `generation` во все WebSocket events — штамп в `send()`, `test_turn_events.py`.
- [x] Сделать server-side VAD с Silero ONNX: `silero_vad.py` + выбор `vad_backend` с прозрачным fallback на `EnergyVad`.
- [x] Собирать p50/p95 latency по фазам (`latency.py`) с бюджетом для отката рискованных оптимизаций.
- [x] Разделить `final transcript`, `interim transcript` и `cancelled` — `interim_transcript`, `transcript: final`, `cancelled`, `test_transcript_split.py`.
- [x] Не запускать preemptive draft для коротких/нестабильных interim — `preemptive_min_chars`, `preemptive_stability_ratio`, `test_preemptive_gating.py`.
- [x] Зафиксировать PCM-протокол в коде: mono PCM16, 32 kHz, WAV собирается на сервере; протокол покрыт `test_pcm_protocol.py` и `test_vad.py`.
- [ ] Снять фактические sample rate, размер кадра AudioWorklet и задержку временных меток на реальном устройстве ввода.
- [x] Интеграционный smoke-тест PCM → WAV → fake batch STT → fake LLM → fake TTS (`test_process_audio_smoke.py`).

## Этап B — Mac SpeechAnalyzer

- [ ] Создать Swift target/plugin в `ui/src-tauri` или отдельном macOS package.
- [ ] Реализовать разрешения микрофона и `SpeechAnalyzer`/`SpeechTranscriber`.
- [ ] Проверить загрузку on-device модели для `ru-RU`.
- [ ] Передавать volatile и finalized transcript через Tauri events.
- [ ] Подключить bridge к `MacSpeechAnalyzerSTT`.
- [ ] Проверить fallback, если модель не установлена или OS API недоступен.
- [ ] Измерить end-to-end latency на M1 Max.

## Этап C — streaming output и качество голоса

- [ ] Выбрать и подключить TTS backend с настоящим chunked output.
- [ ] Выбрать MLX-Audio + Kokoro/MLX-совместимый voice-cloning backend для M1 Max как baseline; не считать CLI `--stream` доказательством streaming HTTP API.
- [ ] Проверить русский TTS: WER не применим, измерять MOS/естественность, first-audio latency, RTF, peak memory и число одновременных запросов.
- [ ] Сравнить Kokoro, Chatterbox и Dia на одинаковых русских фразах; Chatterbox MPS считать отдельным экспериментом, а не гарантированным ускорением.
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
- [ ] First-token, first-audio, total latency benchmarks на реальном железе (сейчас собираются только p50/p95 по фазам).
- [ ] Memory/CPU/GPU profiles для 8B/14B/32B.
- [ ] Piper против Kokoro/MLX-Audio на русском.
- [x] VRM expression capability detection — отчёт покрытия ARKit-52 → морфы модели (`faceMap.faceCoverage`, `scripts/model_capabilities.py`).
- [ ] CSP, Tauri capabilities, WebSocket session token и origin checks.
- [ ] macOS notarization/signing и automated release.

## Этап H — мимика и внешний Audio2Face

Полная оценка направления, требований и ограничений — в [FACE.md](FACE.md).
Основной профиль — MacBook M1 Max 64 ГБ; локальная мимика не должна зависеть от
NVIDIA. Audio2Face-3D рассматривается как отдельный `nvidia-remote` профиль.

- [x] Канонический список ARKit-52 на сервере (`face.py`) и мост ARKit → морфы конкретной модели в UI (`faceMap.ts`) с честным отчётом покрытия.
- [x] Выбор бэкенда мимики `face_backend`, health-probe Audio2Face-3D и отчёт в `liya doctor`.
- [x] Приоритет внешних кадров над процедурной мимикой в риге (`applyArkitFrame`, `EXT_HOLD`) и события `face_frame` / `face_status`.
- [ ] Калибровка гейнов маппинга на реальных кадрах сервиса: сейчас значения обоснованы структурой VRoid-морфов, но не измерены.
- [ ] Развернуть Audio2Face-3D NIM на отдельном Ubuntu/NVIDIA-хосте (не на M1 Max) и реализовать gRPC-клиент `ProcessAudioStream` (нужны `grpcio` и стабы `nvidia_ace`).
- [ ] Провести отдельный Apple Silicon/Core ML research spike для локальной ARKit-мимики, если Audio2Face-профиль недоступен.
- [ ] Поднять покрытие ARKit-52: с текущей моделью маппится 31 шейп из 52, 21 шейп не имеет подходящего морфа; нужен аватар с более полным набором expression targets.
- [ ] Синхронизировать кадры мимики с Web Audio playback по `time_code` (сейчас не проверено).

Audio2Face не заменяет процедурные слои позы головы, корпуса и вторичной анимации. Конкретный набор осмысленных blendshape-каналов и качество `EyeLook*`/`Head*` нужно проверить на выбранной версии NIM и модели; ограничение 21 unmapped shape относится к текущей `Lia.gltf`, а не к Audio2Face.

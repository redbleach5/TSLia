# Лия (TSLia)

Локальный голосовой ИИ-компаньон Лия. Основной пользовательский путь: микрофон → PCM → локальный STT → LLM → TTS → Web Audio → glTF-аватар.

> **Статус:** рабочий вертикальный прототип, не production-ready ассистент. Точная карта возможностей и ограничений находится в [docs/STATUS.md](docs/STATUS.md), план — в [docs/ROADMAP.md](docs/ROADMAP.md).

## Что реально работает

- локальный OpenAI-совместимый LLM endpoint;
- локальный batch STT endpoint с selectable backend-контрактом;
- локальный batch TTS endpoint;
- Tauri 2 + React + TypeScript desktop UI;
- 3D-аватар в формате glTF через Three.js `GLTFLoader`;
- микрофонный PCM transport через `AudioWorklet` (mono PCM16, 32 kHz);
- WebSocket runtime с turn/reply/generation guardrails;
- SSE LLM, sentence buffer и ordered Web Audio playback;
- базовая SQLite facts memory с просмотром и удалением;
- capability policy, которая не объявляет batch STT/TTS настоящими streaming backend;
- контракт `MacSpeechAnalyzerSTT` с fallback на `LocalHttpSTT`;
- server-side endpointing по PCM с выбором VAD-backend: `energy` или Silero ONNX (`vad_backend`), с прозрачным fallback на energy при отсутствии модели или `onnxruntime`;
- latency p50/p95 по фазам stt/llm/tts/total в событии `latency_stats` и бюджет отката `latency_p95_budget_ms`.

## Что ещё не готово

- native macOS `SpeechAnalyzer` bridge;
- incremental STT с volatile/final transcript;
- production server-side VAD/endpointing;
- настоящий streaming TTS;
- автоматический barge-in и wake word;
- RAG, MCP и опасные инструменты;
- production security/session authentication.

Не путайте следующие понятия:

```text
PCM transport ≠ streaming STT
SSE LLM ≠ streaming TTS
Web Audio queue ≠ streaming TTS synthesis
```

Подробности: [docs/STATUS.md](docs/STATUS.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) и [docs/FACE.md](docs/FACE.md).

## Требования

- Python 3.11+;
- Node.js для UI;
- Rust toolchain для Tauri;
- macOS/Xcode для нативного SpeechAnalyzer bridge;
- Apple Silicon; **основной профиль — MacBook M1 Max с 64 ГБ unified memory**;
- локальные LLM, STT и TTS services;
- Audio2Face-3D локально на этом Mac не поддерживается: для него нужен отдельный NVIDIA/CUDA-хост либо облачный NVCF.

## Быстрый запуск CLI

```bash
git clone https://github.com/redbleach5/TSLia.git
cd TSLia
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config.example.json config.json
liya doctor
liya chat
```

`config.json` игнорируется Git. Не добавляйте в него секреты.

## Локальные endpoint-ы

По умолчанию:

| Сервис | Endpoint | Режим |
|---|---|---|
| LLM | `http://127.0.0.1:8080/v1/chat/completions` | OpenAI-compatible, SSE поддерживается |
| STT | `http://127.0.0.1:8081/v1/audio/transcriptions` | batch |
| TTS | `http://127.0.0.1:8082/v1/audio/speech` | batch WAV |

Параметры `stt_backend` и capability описаны в [config.example.json](config.example.json).

Для `vad_backend = "silero"` нужны `pip install onnxruntime` и файл модели `silero_vad.onnx` (репозиторий `snakers4/silero-vad`) по пути `vad_model_path`. Если модели или рантайма нет, endpointing не ломается: сессия остаётся на энергетическом пороге `vad_threshold`.

## Запуск desktop UI

Backend runtime:

```bash
python -m pip install -e '.[ui]'
python -m liya.ui_runtime
```

Frontend:

```bash
cd ui
npm install
npm run dev
```

Откройте `http://127.0.0.1:1420`. Для Tauri:

```bash
cd ui
npx tauri dev
```

UI использует PCM через `AudioWorklet`; WebM оставлен только как совместимый fallback в backend-контуре. Воспроизведение идёт через Web Audio queue, а не через последовательную замену `<audio>.src`.

## macOS

Основной профиль: MLX-LM, локальный STT/TTS, позднее SpeechAnalyzer. Подробности: [docs/MACOS.md](docs/MACOS.md).

## WSL 2

WSL используется для llama.cpp/GGUF, тестов и переносимости. MLX недоступен внутри WSL. Подробности: [docs/WSL.md](docs/WSL.md).

## Команды

```bash
liya doctor
liya chat
liya ask "Привет, Лия"
liya say-file recording.wav
liya record data/recording.wav
```

## Проверки

```bash
python -m compileall -q src
pytest -q
cd ui && npm run build
cd src-tauri && cargo check
```

## Структура

```text
src/liya/       Python runtime, CLI, clients, STT/VAD abstraction, latency-метрики
ui/src/         React UI, Three.js/glTF, AudioWorklet, Web Audio queue
ui/src-tauri/   Tauri shell
tests/          unit и protocol tests
scripts/        WSL/llama.cpp helpers
docs/           архитектура, статус, платформы и roadmap
```

## Лицензия

MIT. Проверяйте лицензии отдельно подключаемых моделей, голосов и runtime-зависимостей.

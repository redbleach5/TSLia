# Лия (TSLia)

Локальный голосовой ИИ-компаньон с русскоязычным режимом по умолчанию. Репозиторий содержит первый MVP: локальный HTTP-контур STT → LLM → TTS, текстовый диалог, обработку WAV-файла и JSONL-историю разговоров.

> Статус: ранний MVP. Голосовой ввод с микрофона, VAD, streaming и barge-in находятся в roadmap.

## Возможности

- локальный LLM через OpenAI-совместимый API;
- локальный STT через `/v1/audio/transcriptions`;
- локальный TTS через `/v1/audio/speech`;
- текстовый режим `liya chat`;
- один запрос `liya ask`;
- обработка аудиофайла `liya say-file`;
- профиль личности Лии;
- история диалога в `data/conversation.jsonl`;
- отдельные профили macOS/MLX и WSL/llama.cpp.
- запись микрофона в WAV командой `liya record` (опционально требуется `sounddevice`);
- энергетический VAD-lite с завершением после тишины;
- очередь голосовых заданий и отмена ответа через `VoicePipeline`;
- unit-тесты аудио и voice pipeline;

## Требования

- Python 3.11+;
- macOS с Apple Silicon для основного голосового профиля;
- WSL 2 Ubuntu для универсального профиля;
- локальные LLM, STT и TTS-сервисы.

## Быстрый запуск

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

`config.json` игнорируется Git. Не добавляйте в него API-ключи или секреты.

## Локальные endpoint-ы

По умолчанию:

| Сервис | Endpoint |
|---|---|
| LLM | `http://127.0.0.1:8080/v1/chat/completions` |
| STT | `http://127.0.0.1:8081/v1/audio/transcriptions` |
| TTS | `http://127.0.0.1:8082/v1/audio/speech` |

Перед началом диалога запустите локальные сервисы и проверьте их командой:

```bash
liya doctor
```

## macOS

Основной профиль для M1 Max использует MLX-LM. Подробная инструкция: [docs/MACOS.md](docs/MACOS.md).

```bash
mlx_lm.server --model mlx-community/Qwen3-8B-Instruct-4bit --port 8080
```

Для TTS можно использовать Piper как стабильный baseline или MLX-Audio/Kokoro после проверки русского голоса.

## WSL 2

WSL-профиль использует llama.cpp и GGUF:

```bash
./scripts/check-wsl.sh
./scripts/setup-wsl.sh
./scripts/run-llama.sh /home/user/liya/models/model.gguf
```

Подробная инструкция: [docs/WSL.md](docs/WSL.md).

## Команды

```bash
liya doctor                         # показать конфигурацию сервисов
liya chat                           # интерактивный текстовый диалог
liya ask "Привет, Лия"              # один запрос
liya say-file recording.wav         # WAV → STT → LLM → TTS
```
liya record data/recording.wav          # запись микрофона в WAV
liya say-file path/to/recording.wav      # WAV → STT → LLM → TTS

## Проверки

```bash
python -m compileall -q src
pytest -q
```

## Структура

```text
src/liya/          ядро приложения и CLI
tests/             unit-тесты
scripts/           WSL и llama.cpp helpers
config.example.json  безопасный шаблон конфигурации
docs/              архитектура и инструкции
```

## Дорожная карта

1. Подключить реальный микрофон и push-to-talk.
2. Добавить VAD и endpointing.
3. Добавить streaming STT/LLM/TTS.
4. Реализовать barge-in и отмену ответа.
5. Добавить память пользователя и RAG.
6. Подключить MCP-инструменты с подтверждением опасных действий.
7. Добавить нативный Swift-клиент и wake word.

См. [docs/ROADMAP.md](docs/ROADMAP.md).
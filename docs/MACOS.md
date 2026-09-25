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

Для M1 Max с 64 ГБ это основной профиль проекта. Можно начать с 8B/4-bit,
затем сравнить 14B или 20–32B по задержке и качеству. Unified memory полезна
для LLM, STT и TTS, но это не CUDA-память: локальный Audio2Face-3D NIM на этом
Mac не запускается, поскольку NIM требует NVIDIA GPU/CUDA/Docker. Основной
локальный профиль использует процедурный риг и базовый анализ звука; Audio2Face
остаётся отдельным удалённым NVIDIA-профилем.

## STT

Нужен сервер с OpenAI-совместимым endpoint `POST /v1/audio/transcriptions`. Подойти может адаптер над whisper.cpp или MLX-Audio Whisper.

Для M1 Max 64 ГБ основной кандидат — MLX-Audio server с MLX-версией Whisper, например
`mlx-community/whisper-large-v3-turbo-asr-fp16`:

```bash
pip install mlx-audio
mlx_audio.server --host 127.0.0.1 --port 8000
```

В `config.json` можно указать отдельный endpoint Лии:

```json
{
  "stt_backend": "local_http",
  "stt_url": "http://127.0.0.1:8000/v1/audio/transcriptions",
  "tts_url": "http://127.0.0.1:8000/v1/audio/speech"
}
```

Один MLX-Audio server может обслуживать TTS и STT, но на практике его необходимо
отдельно проверить на M1 Max: память, время первой загрузки модели, качество русского
языка и конкуренция моделей при одновременной работе с MLX-LM. Не считать Whisper
настоящим incremental backend только потому, что MLX-Audio умеет обрабатывать аудио.

Apple Speech (`SFSpeechRecognizer`/`SFSpeechAudioBufferRecognitionRequest`) — отдельный
нативный кандидат с потенциально низкой задержкой и on-device режимом. Он требует
разрешения микрофона/речи, доступности языковой модели и проверки поведения конкретной
версии macOS. В текущем проекте Swift bridge отсутствует; сторонний plugin bitHuman
не является встроенным backend Лии и не должен добавляться без проверки лицензии,
совместимости и протокола.

## TTS

Baseline: Piper. Для более естественного голоса на M1 Max первый кандидат —
MLX-Audio с Kokoro; для voice cloning нужно отдельно выбрать MLX-совместимую модель
и зафиксировать версию, reference audio и правила хранения голоса. MLX-Audio
документирует Kokoro, Chatterbox и Dia, а также запуск stream-команд CLI, однако
наличие `--stream` у CLI не означает, что OpenAI-compatible HTTP endpoint Лии
отдаёт корректный chunked TTS stream. Текущий клиент Лии считает TTS streaming только
после проверки фактического протокола.

```bash
mlx_audio.tts.generate --model mlx-community/Kokoro-82M-bf16 --text "Привет, я Лия" --stream
```

Русские голоса необходимо проверить отдельно. На M1 Max TTS должен отдавать
WAV/chunks с фактическим sample rate: эти метаданные понадобятся и локальному
анализу амплитуды, и внешнему Audio2Face-профилю. Не обещать одинаковое качество
и скорость для всех моделей: измерять нужно отдельно, включая первую загрузку,
RTF, память, WER/CER и естественность.

Chatterbox официально имеет macOS-пример с выбором `mps`, если MPS доступен. Это
подтверждает возможность запуска через MPS, но не подтверждает отдельный
«Apple Silicon Optimization»-релиз или гарантированные 2–3× ускорение и −50% RAM.
Для Лии Chatterbox следует оценивать как альтернативный TTS backend, а не как
обязательную замену Kokoro.

## Мимика и Audio2Face

Нативный Audio2Face-3D NIM не является частью локального Mac-профиля: M1 Max
имеет Apple GPU, а NIM 2.0 требует NVIDIA CUDA. Для него нужен отдельный
Ubuntu/NVIDIA-хост; из Mac приложение может обращаться к такому сервису по gRPC.
На самом Mac используются процедурный avatarRig и RMS/спектральный lip sync.
Если нужна ARKit-мимика без NVIDIA-хоста, следует отдельно оценить совместимый
Core ML/Apple Silicon backend; Audio2X SDK с CUDA для этого профиля также не
подходит.

## Проверка

```bash
liya doctor
liya chat
```

## Следующие шаги

Нативный macOS-клиент должен добавить разрешение микрофона, AVAudioEngine, VAD, push-to-talk и воспроизведение TTS-буферов.
# Мимика лица и NVIDIA Audio2Face-3D

Документ фиксирует границу между уже подготовленным контрактом Лии и реально
проверяемой интеграцией NVIDIA. На дату проверки официальная документация NIM
обновлена 18 марта 2026 года; перед установкой нужно сверить support matrix и
changelog выбранной версии контейнера.

## Что это может дать проекту

Audio2Face-3D NIM принимает речь и необязательную эмоцию, а возвращает временной
поток ARKit-подобных blendshape-весов. Для Лии это заменяет приблизительный
RMS-based lip sync, если сервис сможет анализировать **точный TTS WAV**, который
Web Audio действительно воспроизводит.

Направление полезно для:

- фонемной и эмоциональной мимики рта, бровей, щёк и век;
- сохранения temporal smoothing сервиса;
- отладки качества по помеченным WAV и `time_code`.

Audio2Face не заменяет позу головы, корпуса, взгляд, тени, материалы и вторичную
анимацию волос. Их по-прежнему должен вести `avatarRig.ts`. Нельзя считать, что
конкретная версия сервиса физически не умеет двигать `EyeLook*` или `Head*` без
проверки конкретной модели: документация обещает ARKit-подобный blendshape-вывод.
Нужные шейпы маппятся только при наличии подходящих morph targets модели.

## Профили Apple Silicon и NVIDIA

**Основной профиль проекта — MacBook M1 Max с 64 ГБ unified memory.** На нём
полностью локально работают Python/Tauri/UI, MLX-LM, Apple/CPU-адаптеры STT и
TTS, Web Audio и процедурный avatarRig. Память общего объёма позволяет выбирать
размер LLM, но не превращает Mac в CUDA-узел.

Audio2Face-3D NIM 2.0 — **не локальный компонент M1 Max**. Поддерживаемая
схема NIM требует NVIDIA GPU, CUDA 12.8+, Docker и NVIDIA Container Toolkit.
Поэтому для Лии определены два профиля:

- `mac-local` — основной, без NVIDIA: процедурная анимация и базовый lip sync;
- `nvidia-remote` — опциональный, Audio2Face-3D на отдельном Ubuntu/NVIDIA-хосте,
  с которым Mac общается по gRPC.

NVCF также является удалённым облачным вариантом, а не локальным ускорением на
Apple GPU. Audio2X SDK 2.x ориентирован на NVIDIA CUDA и не исправляет эту
несовместимость. Если локальная ARKit-мимика на Mac станет обязательной, нужен
отдельный Core ML/Apple Silicon research spike; подменять его неисполненным
вызовом NIM нельзя.

## Варианты NVIDIA

| Вариант | Когда использовать | Ограничение для Лии |
|---|---|---|
| Audio2Face-3D NIM 2.0 через gRPC | удалённый Linux/NVIDIA-хост | не работает локально на M1 Max; нужны NVIDIA GPU, Docker, NGC key/лицензия |
| NVIDIA Cloud Function | нет собственного NVIDIA-хоста | API key, function id, сетевая зависимость и передача аудио/лица наружу |
| Audio2X SDK 2.x | нативная C++/CUDA-интеграция на NVIDIA-хосте | не Apple Silicon, отдельная лицензия и сложнее интеграция с Python/Tauri |

Официальный NIM support matrix для 2.0: тестированная ОС Ubuntu 24.04; CUDA
`>=12.8,<13.0` (рекомендуется 12.9), NVIDIA driver R570+ (рекомендуется R580),
TensorRT `>=10.13,<11.0` внутри контейнера и Docker с NVIDIA Container Toolkit.
Есть готовые профили для A10G, A30, L4, L40S, RTX 4090, RTX 5080, RTX 5090,
RTX 6000 Ada, RTX PRO 6000 Blackwell и B200. Сервис рассчитан на один GPU;
для нескольких GPU нужны несколько экземпляров. NVIDIA отдельно запрещает
использовать ПО для самостоятельного распознавания эмоций; сервис следует
интегрировать в общий voice runtime согласно документации.

Текущий Windows-профиль может оставить Python/UI на Windows, а NIM запустить в
WSL2 Ubuntu 24.04. Для production-подобной конфигурации лучше ставить сервис на
отдельную Linux-машину: проброс CUDA через WSL и проброс gRPC через `localhost`
требуют отдельной проверки версии драйвера и firewall. Нельзя считать
`127.0.0.1:52000` гарантированно доступным между двумя разными WSL-дистрибутивами.

## Точный gRPC-контракт

Версия 2.0 сохраняет имя совместимости `service.a2f_controller`, но отдельный
Audio2Face Controller больше не нужен. Legacy unidirectional RPC удалены; нужен
bidirectional RPC:

```text
package nvidia_ace.services.a2f_controller.v1
service A2FControllerService
rpc ProcessAudioStream(stream AudioStream) returns (stream AnimationDataStream)
```

Протокол:

1. первым сообщением отправить `AudioStreamHeader`;
2. передать один или несколько `AudioWithEmotion`;
3. обязательно завершить поток пустым `AudioStream.EndOfAudio`;
4. читать `AnimationDataStream`, извлекать blendshape weights и `time_code`;
5. после завершения проверить gRPC status `SUCCESS`.

Пример NVIDIA использует Python wheel `nvidia_ace-1.2.0`, но версия wheel не
равна версии NIM. Стабы и контракт нужно закреплять вместе с контейнером, а не
подменять самодельными сообщениями. Один audio buffer ограничен 10 секундами,
весь clip — 300 секундами. Официальный пример использует mono PCM16, 16 kHz;
частота ответа TTS сейчас не гарантированно равна 16 kHz, поэтому клиент должен
пересемплировать с фактического `sampleRate` WAV.

Health-check NIM доступен без Python wheel:

```text
http://127.0.0.1:8000/v1/health/ready
```

`liya doctor` уже проверяет этот endpoint. `face_backend = "audio2face"`
также требует установленные `grpcio` и `nvidia_ace`. До реализации RPC это честно
означает «бэкенд выбран, transport ещё не готов», а не работающую мимику.


## Целевой поток

```text
TTS WAV bytes + фактический sample rate
  → A2F-3D ProcessAudioStream (один stream на фразу/reply)
  → ARKit weights + time_code
  → WebSocket face_frame с reply_id/turn_id
  → UI queue кадров
  → ARKit → Fcl_* mapping
  → Three.js morph targets
```

A2F нужно отправлять до `audio`-события, но WebSocket events не гарантируют, что
браузер уже создал `AudioBuffer` и вызвал `source.start(at)`. Сейчас
`AudioPlaybackQueue` не публикует фактическое время начала и не хранит
`time_code` относительно replay-clock. Поэтому простая отправка `face_frame`
вместе с WAV даст сетевой и queue jitter.

Правильная следующая реализация:

1. расширить audio event полями `reply_id`, `index` и аудиодлительностью;
2. при `schedule(0)` вычислить `playbackStart = nextAt` в координатах
   `AudioContext.currentTime` и сообщить UI через `audio_started`;
3. хранить face-кадры в очереди по `reply_id`/`index` с абсолютным replay time;
4. в render loop выбирать кадр по `AudioContext.currentTime`, а не применять
   последний пришедший кадр немедленно;
5. при `clear/cancel` удалить face queue и закрыть gRPC stream;
6. для нескольких параллельных TTS-фраз учитывать `index` и общий reply timeline.

До этого `EXT_HOLD` в риге — временный fallback, а не доказательство
синхронизации.

## Текущий аватар

`ui/src/faceMap.ts` сопоставляет 31 из 52 ARKit-шейпов с существующими
`Fcl_*` morph targets текущей `Lia.gltf`; 21 шейп явно помечен unmapped. Это
ограничение аватара, а не заявленный лимит Audio2Face. Для более полного лица
нужен glTF/VRM с полным или близким к ARKit набором expression targets.
`faceCoverage()` проверяет одновременно наличие target в файле модели.

Гейны 0.35–1.0 сейчас структурные, не измеренные по видео. Калибровать их нужно
на фиксированном наборе русских фраз, сравнивая A2F output с рассчитанными
facial action/intensity метриками и визуально проверяя перекрытия морфов.

## Безопасность и приватность

- Не передавать API keys в config-фронтенд или WebSocket event.
- Для localhost достаточно непубликовать порты; для удалённого сервиса нужны
  TLS, ограничение адреса назначения и проверка server identity.
- NVCF означает отправку речи и, вероятно, данных аватара во внешний сервис.
  Для локального/приватного профиля это отдельное продуктовое решение.
- `face_frame` может содержать чувствительную биометрически интерпретируемую
  мимику; не логировать сырые веса без необходимости.
- Не считать HTTP health успешным доказательством работающего inference: нужны
  отдельные `ProcessAudioStream` integration tests и тайминги.

## Следующий этап и критерии готовности

1. Зафиксировать версии NIM image, wheel, CUDA/driver и модель в lock-файле
   профиля окружения.
2. Добавить optional extra с `grpcio`; `nvidia_ace` устанавливать из
   документированного NVIDIA wheel, не публикуя или не пересобирая стабы без
   необходимости.
3. Реализовать один async stream на TTS WAV, корректные header/EOA/status и
   backpressure.
4. Подключить `reply_id` к каждому кадру и удалять поток при cancel.
5. Ввести replay-clock синхронизацию вместо немедленного `applyArkitFrame`.
6. Проверить integration test против NIM, а mocks оставить для обычного CI.
7. На реальном GPU измерить first animation frame, p50/p95 frame latency, число
   одновременных streams, VRAM и качество на русском TTS.

Только после этих пунктов `face_backend = "audio2face"` можно переименовать из
интеграционного намерения в рабочий runtime.

## Источники

- [Audio2Face-3D NIM overview](https://docs.nvidia.com/nim/digital-human/a2f-3d/latest/index.html)
- [Getting Started and usage restrictions](https://docs.nvidia.com/ace/audio2face-3d-microservice/latest/text/getting-started/getting-started.html)
- [gRPC ProcessAudioStream contract](https://docs.nvidia.com/ace/audio2face-3d-microservice/latest/text/interacting/a2f-rpc.html)
- [Support Matrix](https://archive.docs.nvidia.com/ace/audio2face-3d-microservice/2.0/text/support-matrix.html)
- [Audio2X SDK](https://github.com/NVIDIA/Audio2Face-3D-SDK)

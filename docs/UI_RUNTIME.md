# UI runtime

## Capture

Основной браузерный путь:

```text
getUserMedia
→ AudioContext({ sampleRate: 32000 })
→ AudioWorklet
→ Float32 frames
→ Int16 PCM
→ audio_pcm_chunk WebSocket events
```

`MediaRecorder`/WebM оставлен совместимым fallback в backend, но не является основным PCM-путём UI.

## Playback

TTS chunks декодируются через `decodeAudioData` и планируются `AudioBufferSourceNode` в порядке `index`. Аудио не озвучивается через последовательную замену `<audio>.src`. `AnalyserNode` подключён к queue и используется для базового lip sync (morph targets аватара).

## Аватар

Анимационных клипов в `Lia.gltf` нет (экспорт в T-позе), поэтому «жизнь» аватара
процедурная и живёт в `ui/src/avatarRig.ts`, покадрово на костях и morph targets:

- дыхание: несимметричный цикл (вдох 35%), разная частота по состояниям, подъём
  плеч трансляцией ключицы, наклон грудной клетки и вертикальный bob сцены;
- перенос веса с ноги на ногу каждые 6–14 с с контрповоротом корпуса (контрпост);
- поза и мимика состояний (`idle/listening/thinking/speaking/error`) сглаживаются
  ~2.2/с, поэтому переход не «телепортирует» персонажа;
- взгляд: саккады к случайной точке с привязкой к состоянию, микродрейф,
  моргание со случайными интервалами, двойными и редкими «сонными» моргами;
- артикуляция: RMS тайм-домена `AnalyserNode` → огибающая с быстрой атакой и
  медленным спадом, morph `Fcl_MTH_A` плюс небольшой `Fcl_MTH_O` на широком рту;
- микро-кивки в «слушании» и речи, расслабленная кисть (полу-сжатые пальцы),
  инерция рук и вторичная динамика волос на пружинах от угловой скорости головы.

## Capability policy

- `local_http` STT — batch.
- `stt_stream=true` — только настоящий incremental backend.
- `tts_stream=true` — только backend, который отдаёт аудио по мере синтеза.
- PCM transport сам по себе не означает live recognition.

Подробности: [ARCHITECTURE.md](ARCHITECTURE.md) и [STATUS.md](STATUS.md).

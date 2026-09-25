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

TTS chunks декодируются через `decodeAudioData` и планируются `AudioBufferSourceNode` в порядке `index`. Аудио не озвучивается через последовательную замену `<audio>.src`. `AnalyserNode` подключён к queue и используется для базового VRM lip sync.

## Capability policy

- `local_http` STT — batch.
- `stt_stream=true` — только настоящий incremental backend.
- `tts_stream=true` — только backend, который отдаёт аудио по мере синтеза.
- PCM transport сам по себе не означает live recognition.

Подробности: [ARCHITECTURE.md](ARCHITECTURE.md) и [STATUS.md](STATUS.md).

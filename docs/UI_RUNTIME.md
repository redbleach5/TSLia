"""UI runtime notes: PCM-first microphone transport and Web Audio playback.

Runtime capability policy:
- local HTTP STT is batch by default;
- `ServiceCapabilities.stt_stream` must be enabled only by a real incremental backend;
- PCM transport is independent from STT transport and must not be confused with live decoding;
- TTS remains batch until a real chunked/streaming provider is configured.
"""

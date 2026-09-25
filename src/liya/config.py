from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class Settings:
    llm_url: str
    stt_url: str
    tts_url: str
    model: str
    language: str
    voice: str
    max_history_messages: int
    audio_output_path: Path
    stt_backend: str = "local_http"
    stt_model: str = "whisper-large-v3-turbo"
    tts_backend: str = "local_http"
    tts_model: str = "kokoro"
    voice_reference_path: str = ""
    mlx_audio_url: str = "http://127.0.0.1:8000"
    vad_threshold: float = 0.025
    vad_min_speech_ms: int = 300
    vad_min_silence_ms: int = 850
    vad_max_seconds: int = 30
    vad_endpointing: bool = True
    vad_backend: str = "energy"
    vad_model_path: str = "models/silero_vad.onnx"
    vad_silero_threshold: float = 0.5
    stt_partial_interval_ms: int = 800
    stt_partial_min_bytes: int = 32000
    stt_partial_window_seconds: int = 8
    stt_partial_max_calls: int = 6
    stt_partial_min_confidence: float = 0.35
    request_timeout_seconds: float = 30.0
    preemptive_min_chars: int = 12
    preemptive_max_sentences: int = 4
    preemptive_stability_ratio: float = 0.5
    latency_window: int = 200
    latency_p95_budget_ms: int = 4000
    latency_min_samples: int = 5
    face_backend: str = "ui"
    a2f_url: str = "127.0.0.1:52000"
    a2f_health_url: str = "http://127.0.0.1:8000/v1/health/ready"

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return cls(llm_url=data["llm_url"], stt_url=data["stt_url"], tts_url=data["tts_url"], model=data["model"], language=data["language"], voice=data["voice"], max_history_messages=int(data["max_history_messages"]), audio_output_path=Path(data["audio_output_path"]), stt_backend=str(data.get("stt_backend", "local_http")), stt_model=str(data.get("stt_model", "whisper-large-v3-turbo")), tts_backend=str(data.get("tts_backend", "local_http")), tts_model=str(data.get("tts_model", "kokoro")), voice_reference_path=str(data.get("voice_reference_path", "")), mlx_audio_url=str(data.get("mlx_audio_url", "http://127.0.0.1:8000")), vad_threshold=float(data.get("vad_threshold", 0.025)), vad_min_speech_ms=int(data.get("vad_min_speech_ms", 300)), vad_min_silence_ms=int(data.get("vad_min_silence_ms", 850)), vad_max_seconds=int(data.get("vad_max_seconds", 30)), vad_endpointing=bool(data.get("vad_endpointing", True)), vad_backend=str(data.get("vad_backend", "energy")), vad_model_path=str(data.get("vad_model_path", "models/silero_vad.onnx")), vad_silero_threshold=float(data.get("vad_silero_threshold", 0.5)), stt_partial_interval_ms=int(data.get("stt_partial_interval_ms", 800)), stt_partial_min_bytes=int(data.get("stt_partial_min_bytes", 32000)), stt_partial_window_seconds=int(data.get("stt_partial_window_seconds", 8)), stt_partial_max_calls=int(data.get("stt_partial_max_calls", 6)), stt_partial_min_confidence=float(data.get("stt_partial_min_confidence", 0.35)), request_timeout_seconds=float(data.get("request_timeout_seconds", 30.0)), preemptive_min_chars=int(data.get("preemptive_min_chars", 12)), preemptive_max_sentences=int(data.get("preemptive_max_sentences", 4)), preemptive_stability_ratio=float(data.get("preemptive_stability_ratio", 0.5)), latency_window=int(data.get("latency_window", 200)), latency_p95_budget_ms=int(data.get("latency_p95_budget_ms", 4000)), latency_min_samples=int(data.get("latency_min_samples", 5)), face_backend=str(data.get("face_backend", "ui")), a2f_url=str(data.get("a2f_url", "127.0.0.1:52000")), a2f_health_url=str(data.get("a2f_health_url", "http://127.0.0.1:8000/v1/health/ready")))

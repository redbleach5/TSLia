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
    vad_threshold: float = 0.025
    vad_min_speech_ms: int = 300
    vad_min_silence_ms: int = 850
    vad_max_seconds: int = 30
    stt_partial_interval_ms: int = 800
    stt_partial_min_bytes: int = 32000
    stt_partial_window_seconds: int = 8
    stt_partial_max_calls: int = 6
    stt_partial_min_confidence: float = 0.35
    request_timeout_seconds: float = 30.0
    preemptive_min_chars: int = 12
    preemptive_max_sentences: int = 4

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(llm_url=data["llm_url"], stt_url=data["stt_url"], tts_url=data["tts_url"], model=data["model"], language=data["language"], voice=data["voice"], max_history_messages=int(data["max_history_messages"]), audio_output_path=Path(data["audio_output_path"]), vad_threshold=float(data.get("vad_threshold", 0.025)), vad_min_speech_ms=int(data.get("vad_min_speech_ms", 300)), vad_min_silence_ms=int(data.get("vad_min_silence_ms", 850)), vad_max_seconds=int(data.get("vad_max_seconds", 30)), stt_partial_interval_ms=int(data.get("stt_partial_interval_ms", 800)), stt_partial_min_bytes=int(data.get("stt_partial_min_bytes", 32000)), stt_partial_window_seconds=int(data.get("stt_partial_window_seconds", 8)), stt_partial_max_calls=int(data.get("stt_partial_max_calls", 6)), stt_partial_min_confidence=float(data.get("stt_partial_min_confidence", 0.35)), request_timeout_seconds=float(data.get("request_timeout_seconds", 30.0)), preemptive_min_chars=int(data.get("preemptive_min_chars", 12)), preemptive_max_sentences=int(data.get("preemptive_max_sentences", 4)))

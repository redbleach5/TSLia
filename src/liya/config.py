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

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(llm_url=data["llm_url"], stt_url=data["stt_url"], tts_url=data["tts_url"], model=data["model"], language=data["language"], voice=data["voice"], max_history_messages=int(data["max_history_messages"]), audio_output_path=Path(data["audio_output_path"]), vad_threshold=float(data.get("vad_threshold", 0.025)), vad_min_speech_ms=int(data.get("vad_min_speech_ms", 300)), vad_min_silence_ms=int(data.get("vad_min_silence_ms", 850)), vad_max_seconds=int(data.get("vad_max_seconds", 30)))

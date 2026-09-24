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

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(llm_url=data["llm_url"], stt_url=data["stt_url"], tts_url=data["tts_url"], model=data["model"], language=data["language"], voice=data["voice"], max_history_messages=int(data["max_history_messages"]), audio_output_path=Path(data["audio_output_path"]))

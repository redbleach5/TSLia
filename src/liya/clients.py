from __future__ import annotations
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from .config import Settings

class LocalServiceError(RuntimeError): pass

class LocalClients:
    def __init__(self, settings: Settings) -> None: self.settings = settings

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload = {"model": self.settings.model, "messages": messages, "temperature": 0.7, "stream": False}
        request = urllib.request.Request(self.settings.llm_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response: data = json.loads(response.read())
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc: raise LocalServiceError(f"LLM недоступен: {self.settings.llm_url}") from exc

    def transcribe(self, audio_path: str | Path) -> str:
        path = Path(audio_path); boundary = "----LiyaBoundary7MA4YWxkTrZu0gW"; audio = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {content_type}\r\n\r\n").encode() + audio + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{self.settings.language}\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(self.settings.stt_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response: return json.loads(response.read())["text"].strip()
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc: raise LocalServiceError(f"STT недоступен: {self.settings.stt_url}") from exc

    def speak(self, text: str, output_path: str | Path | None = None) -> Path:
        path = Path(output_path or self.settings.audio_output_path); path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.settings.voice, "input": text, "voice": self.settings.voice}
        request = urllib.request.Request(self.settings.tts_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response: path.write_bytes(response.read())
        except (urllib.error.URLError, TimeoutError) as exc: raise LocalServiceError(f"TTS недоступен: {self.settings.tts_url}") from exc
        return path

from __future__ import annotations
import json
import mimetypes
import urllib.error
import urllib.request
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator
from .config import Settings

@dataclass(frozen=True)
class ServiceCapabilities:
    llm_stream: bool = True
    stt_stream: bool = False
    tts_stream: bool = False

class LocalServiceError(RuntimeError): pass

class LocalClients:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.capabilities = ServiceCapabilities()

    def _backend_url(self, configured: str, backend: str, path: str) -> str:
        if backend in {"mlx_audio", "mlx-audio"}:
            return self.settings.mlx_audio_url.rstrip("/") + path
        return configured

    def _timeout(self) -> float:
        return float(getattr(self.settings, "request_timeout_seconds", 30.0))

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload = {"model": self.settings.model, "messages": messages, "temperature": 0.7, "stream": False}
        request = urllib.request.Request(self.settings.llm_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response: data = json.loads(response.read())
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc: raise LocalServiceError(f"LLM недоступен: {self.settings.llm_url}") from exc

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        payload = {"model": self.settings.model, "messages": messages, "temperature": 0.7, "stream": True}
        request = urllib.request.Request(self.settings.llm_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"): continue
                    data = line[5:].strip()
                    if data == "[DONE]": break
                    event = json.loads(data)
                    delta = event.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta: yield delta
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LocalServiceError(f"LLM stream недоступен: {self.settings.llm_url}") from exc

    def transcribe(self, audio_path: str | Path) -> str:
        path = Path(audio_path); boundary = "----LiyaBoundary7MA4YWxkTrZu0gW"; audio = path.read_bytes()
        stt_backend = str(getattr(self.settings, "stt_backend", "local_http") or "local_http").lower()
        stt_url = self._backend_url(self.settings.stt_url, stt_backend, "/v1/audio/transcriptions")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {content_type}\r\n\r\n").encode() + audio + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self.settings.stt_model}\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{self.settings.language}\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(stt_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response: return json.loads(response.read())["text"].strip()
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc: raise LocalServiceError(f"STT недоступен: {stt_url}") from exc

    def transcribe_with_confidence(self, audio_path: str | Path) -> tuple[str, float]:
        path = Path(audio_path); boundary = "----LiyaConfidenceBoundary7MA4YWxkTrZu0gW"; audio = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {content_type}\r\n\r\n").encode() + audio + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{self.settings.language}\r\n--{boundary}--\r\n".encode()
        stt_backend = str(getattr(self.settings, "stt_backend", "local_http") or "local_http").lower()
        stt_url = self._backend_url(self.settings.stt_url, stt_backend, "/v1/audio/transcriptions")
        request = urllib.request.Request(stt_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response: data = json.loads(response.read())
            text = str(data.get("text", "")).strip(); confidence = data.get("confidence", data.get("average_logprob", 1.0))
            return text, float(confidence)
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc: raise LocalServiceError(f"STT недоступен: {stt_url}") from exc

    def transcribe_stream(self, audio_path: str | Path) -> Iterator[dict[str, str | bool]]:
        path = Path(audio_path); boundary = "----LiyaStreamBoundary7MA4YWxkTrZu0gW"; audio = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {content_type}\r\n\r\n").encode() + audio + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{self.settings.language}\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"stream\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
        stt_backend = str(getattr(self.settings, "stt_backend", "local_http") or "local_http").lower()
        stt_url = self._backend_url(self.settings.stt_url, stt_backend, "/v1/audio/transcriptions")
        request = urllib.request.Request(stt_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "text/event-stream"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"): continue
                    data = line[5:].strip()
                    if data == "[DONE]": break
                    event = json.loads(data)
                    text = event.get("text", "")
                    if text: yield {"text": str(text), "final": bool(event.get("final", False))}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LocalServiceError(f"STT stream недоступен: {stt_url}") from exc
    def speak(self, text: str, output_path: str | Path | None = None) -> Path:
        path = Path(output_path or self.settings.audio_output_path); path.parent.mkdir(parents=True, exist_ok=True)
        backend = str(getattr(self.settings, "tts_backend", "local_http") or "local_http").lower()
        if backend in {"mlx_audio", "mlx-audio"}:
            # MLX-Audio is served locally through the same OpenAI-compatible WAV
            # endpoint; the model and optional reference voice are request data.
            model = self.settings.tts_model or "kokoro"
        elif backend == "local_http":
            model = self.settings.tts_model or self.settings.voice
        else:
            raise LocalServiceError(f"Неизвестный TTS backend: {backend}")
        payload = {"model": model, "input": text, "voice": self.settings.voice, "language": self.settings.language}
        if self.settings.voice_reference_path: payload["reference_audio"] = self.settings.voice_reference_path
        self.last_tts_payload = payload
        tts_url = self._backend_url(self.settings.tts_url, backend, "/v1/audio/speech")
        request = urllib.request.Request(tts_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response: path.write_bytes(response.read())
        except (urllib.error.URLError, TimeoutError) as exc: raise LocalServiceError(f"TTS недоступен: {tts_url}") from exc
        return path

    def speak_stream(self, text: str) -> Iterator[bytes]:
        backend = str(getattr(self.settings, "tts_backend", "local_http") or "local_http").lower()
        if backend not in {"local_http", "mlx_audio", "mlx-audio"}:
            raise LocalServiceError(f"Неизвестный TTS backend: {backend}")
        payload = {"model": self.settings.tts_model or self.settings.voice, "input": text, "voice": self.settings.voice, "language": self.settings.language, "stream": True}
        if self.settings.voice_reference_path: payload["reference_audio"] = self.settings.voice_reference_path
        tts_url = self._backend_url(self.settings.tts_url, backend, "/v1/audio/speech")
        request = urllib.request.Request(tts_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Accept": "audio/wav"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout()) as response: yield from iter(lambda: response.read(8192), b"")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LocalServiceError(f"TTS stream недоступен: {tts_url}") from exc


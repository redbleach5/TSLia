from __future__ import annotations

import asyncio
import base64
import json
import tempfile
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

from .clients import LocalClients, LocalServiceError
from .config import Settings


class LiyaRuntime:
    def __init__(self, clients: LocalClients | None) -> None:
        self.clients = clients
        self.state = "idle"
        self.history: list[dict[str, str]] = []
        self.audio_chunks: dict[int, list[bytes]] = {}
        self.cancel_event: asyncio.Event | None = None
        self.active_reply: str | None = None
        self.active_task: asyncio.Task | None = None

    async def send(self, websocket, event: dict) -> None:
        await websocket.send(json.dumps(event, ensure_ascii=False))

    async def set_state(self, websocket, state: str) -> None:
        self.state = state
        await self.send(websocket, {"type": "state", "state": state})

    async def stream_reply(self, websocket, reply: str, reply_id: str) -> None:
        if not reply: return
        words = reply.split(" ")
        accumulated = ""
        for word in words:
            if self.cancel_event and self.cancel_event.is_set():
                await self.send(websocket, {"type": "cancelled", "reply_id": reply_id})
                return
            accumulated += (" " if accumulated else "") + word
            await self.send(websocket, {"type": "assistant_chunk", "text": accumulated, "reply_id": reply_id})
            await asyncio.sleep(0.035)
        await self.send(websocket, {"type": "assistant_text", "text": reply, "reply_id": reply_id})
        self.cancel_event = None
        self.active_reply = None
        await self.set_state(websocket, "idle")

    async def process_audio(self, websocket, event: dict) -> None:
        request_id = int(event.get("request_id", 0))
        chunks = self.audio_chunks.pop(request_id, [])
        if not chunks or self.clients is None:
            await self.send(websocket, {"type": "error", "message": "Аудиозапрос пуст или STT недоступен"})
            return
        suffix = ".webm" if event.get("format") == "webm" else ".wav"
        path = Path(tempfile.gettempdir()) / f"liya_{request_id}{suffix}"
        path.write_bytes(b"".join(chunks))
        try:
            text = await asyncio.to_thread(self.clients.transcribe, path)
            self.active_reply = f"reply-{request_id}"
            self.cancel_event = asyncio.Event()
            await self.set_state(websocket, "thinking")
            await self.send(websocket, {"type": "transcript", "text": text, "final": True})
            self.history.append({"role": "user", "content": text})
            try:
                messages = [{"role": "system", "content": "Ты — Лия, локальный голосовой компаньон. Отвечай тепло, кратко и естественно."}] + self.history[-12:]
                reply = await asyncio.to_thread(self.clients.chat, messages)
            except LocalServiceError:
                reply = "Я услышала тебя, но локальный LLM сейчас недоступен."
            self.history.append({"role": "assistant", "content": reply})
            self.active_reply = f"reply-{request_id}"
            self.cancel_event = asyncio.Event()
            await self.set_state(websocket, "speaking")
            await self.stream_reply(websocket, reply, self.active_reply)
            if self.cancel_event and self.cancel_event.is_set():
                await self.set_state(websocket, "idle")
            else:
                output = path.with_name(f"liya_reply_{request_id}.wav")
                audio = await asyncio.to_thread(self.clients.speak, reply, output)
                await self.send(websocket, {"type": "audio", "data": base64.b64encode(audio.read_bytes()).decode(), "mime": "audio/wav", "sampleRate": 22050, "reply_id": self.active_reply})
                await self.set_state(websocket, "idle")
        except (LocalServiceError, OSError) as exc:
            await self.send(websocket, {"type": "error", "message": str(exc)})
            await self.set_state(websocket, "error")
        finally:
            path.unlink(missing_ok=True)

    async def handle(self, websocket, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(websocket, {"type": "error", "message": "Некорректное событие"})
            return
        kind = event.get("type")
        if kind == "start_listening":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks[request_id] = []
            await self.set_state(websocket, "listening")
        elif kind == "audio_chunk":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks.setdefault(request_id, []).append(base64.b64decode(event.get("data", "")))
        elif kind == "finish_listening":
            await self.process_audio(websocket, event)
        elif kind == "text":
            await self.process_text(websocket, event)
        elif kind == "cancel":
            if self.cancel_event: self.cancel_event.set()
            if self.active_reply: await self.send(websocket, {"type": "cancelled", "reply_id": self.active_reply})
            await self.set_state(websocket, "idle")
        elif kind == "ping":
            await self.send(websocket, {"type": "pong"})

    async def process_text(self, websocket, event: dict) -> None:
        text = str(event.get("text", "")).strip()
        if not text:
            return
        self.active_reply = f"reply-{int(time.time_ns())}"
        self.cancel_event = asyncio.Event()
        await self.set_state(websocket, "thinking")
        await self.send(websocket, {"type": "transcript", "text": text, "final": True})
        self.history.append({"role": "user", "content": text})
        try:
            if self.clients is None:
                raise LocalServiceError("LLM client is not configured")
            reply = self.clients.chat([{"role": "system", "content": "Ты — Лия, локальный голосовой компаньон. Отвечай тепло, кратко и естественно."}] + self.history[-12:])
        except LocalServiceError:
            reply = "Я получила сообщение, но локальный LLM сейчас недоступен."
        self.history.append({"role": "assistant", "content": reply})
        await self.set_state(websocket, "speaking")
        await self.stream_reply(websocket, reply, self.active_reply or "reply")


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    if websockets is None:
        raise RuntimeError("Install the UI extra: pip install 'liya-voice-assistant[ui]'")
    settings = Settings.load(Path("config.json"))
    runtime = LiyaRuntime(LocalClients(settings))
    async with websockets.serve(runtime.handle, host, port):
        print(f"Liya runtime: ws://{host}:{port}")
        await asyncio.Future()
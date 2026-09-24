from __future__ import annotations

import asyncio
import json
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

from .clients import LocalClients, LocalServiceError
from .config import Settings

class LiyaRuntime:
    def __init__(self, clients: LocalClients) -> None:
        self.clients = clients
        self.state = "idle"
        self.history: list[dict[str, str]] = []

    async def send(self, websocket, event: dict) -> None:
        await websocket.send(json.dumps(event, ensure_ascii=False))

    async def set_state(self, websocket, state: str) -> None:
        self.state = state
        await self.send(websocket, {"type": "state", "state": state})

    async def handle(self, websocket, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(websocket, {"type": "error", "message": "Некорректное событие"})
            return
        kind = event.get("type")
        if kind == "start_listening":
            await self.set_state(websocket, "listening")
        elif kind == "stop_listening":
            await self.set_state(websocket, "idle")
        elif kind == "text":
            text = str(event.get("text", "")).strip()
            if not text: return
            await self.set_state(websocket, "thinking")
            await self.send(websocket, {"type": "transcript", "text": text, "final": True})
            self.history.append({"role": "user", "content": text})
            try:
                if self.clients is None:
                    raise LocalServiceError("LLM client is not configured")
                reply = self.clients.chat([{"role": "system", "content": "Ты — Лия, локальный голосовой компаньон. Отвечай кратко, тепло и естественно."}] + self.history[-12:])
            except LocalServiceError:
                reply = "Я получила сообщение, но локальный LLM сейчас недоступен. Проверь runtime на порту 8080."
            self.history.append({"role": "assistant", "content": reply})
            await self.set_state(websocket, "speaking")
            await self.send(websocket, {"type": "assistant_text", "text": reply})
            await self.set_state(websocket, "idle")
        elif kind == "cancel":
            await self.set_state(websocket, "idle")
        elif kind == "ping":
            await self.send(websocket, {"type": "pong"})

async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    if websockets is None:
        raise RuntimeError("Install the UI extra: pip install 'liya-voice-assistant[ui]'")
    settings = Settings.load(Path("config.json"))
    runtime = LiyaRuntime(LocalClients(settings))
    async with websockets.serve(runtime.handle, host, port):
        print(f"Liya runtime: ws://{host}:{port}")
        await asyncio.Future()
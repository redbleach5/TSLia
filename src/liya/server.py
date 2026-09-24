from __future__ import annotations

import asyncio
import base64
import json
import tempfile
import time
import wave
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

from .clients import LocalClients, LocalServiceError
from .config import Settings


class SentenceBuffer:
    def __init__(self) -> None:
        self.buffer = ""
    def add(self, delta: str) -> str | None:
        self.buffer += delta
        for mark in (".", "!", "?", "вЂ¦", "\n"):
            index = self.buffer.find(mark)
            if index >= 0 and len(self.buffer[:index].strip()) >= 12:
                sentence = self.buffer[:index + 1].strip()
                self.buffer = self.buffer[index + 1:].lstrip()
                return sentence
        return None
    def flush(self) -> str | None:
        sentence = self.buffer.strip()
        self.buffer = ""
        return sentence or None


class LiyaRuntime:
    def __init__(self, clients: LocalClients | None) -> None:
        self.clients = clients
        self.state = "idle"
        self.history: list[dict[str, str]] = []
        self.audio_chunks: dict[int, list[bytes]] = {}
        self.pcm_chunks: dict[int, list[bytes]] = {}
        self.partial_tasks: dict[int, asyncio.Task] = {}
        self.partial_last_ms: dict[int, float] = {}
        self.cancel_event: asyncio.Event | None = None
        self.active_reply: str | None = None
        self.active_task: asyncio.Task | None = None
        self.last_tts_streamed = False
        self.tts_tasks: list[tuple[int, asyncio.Task]] = []
        self._tts_dispatcher: asyncio.Task | None = None

    async def send(self, websocket, event: dict) -> None:
        await websocket.send(json.dumps(event, ensure_ascii=False))

    async def set_state(self, websocket, state: str) -> None:
        self.state = state
        await self.send(websocket, {"type": "state", "state": state})

    async def dispatch_tts(self, websocket, reply_id: str, done: asyncio.Queue[tuple[int, asyncio.Task] | None]) -> None:
        pending: dict[int, asyncio.Task] = {}
        next_index = 0
        while True:
            item = await done.get()
            if item is None:
                if next_index in pending:
                    result = await pending.pop(next_index)
                    if result and not (self.cancel_event and self.cancel_event.is_set()):
                        await self.send(websocket, {"type": "audio", "data": base64.b64encode(result[1]).decode(), "mime": "audio/wav", "sampleRate": 22050, "reply_id": reply_id, "index": next_index})
                return
            index, task = item
            pending[index] = task
            while next_index in pending:
                result = await pending.pop(next_index)
                if result and not (self.cancel_event and self.cancel_event.is_set()):
                    await self.send(websocket, {"type": "audio", "data": base64.b64encode(result[1]).decode(), "mime": "audio/wav", "sampleRate": 22050, "reply_id": reply_id, "index": next_index})
                next_index += 1

    async def synthesize(self, sentence: str, reply_id: str, index: int) -> tuple[int, bytes]:
        output = Path(tempfile.gettempdir()) / f"liya_{reply_id}_{index}.wav"
        try:
            audio = await asyncio.to_thread(self.clients.speak, sentence, output)
            return index, audio.read_bytes()
        finally:
            output.unlink(missing_ok=True)


    async def stream_reply(self, websocket, messages: list[dict[str, str]], reply_id: str) -> str:
        self.last_tts_streamed = False
        self._websocket = websocket
        self.tts_tasks = []
        self._tts_dispatcher = None
        tts_done: asyncio.Queue[tuple[int, asyncio.Task] | None] = asyncio.Queue()
        self._tts_dispatcher = asyncio.create_task(self.dispatch_tts(websocket, reply_id, tts_done))
        reply = ""
        sentence_buffer = SentenceBuffer()
        if not self.clients:
            await self.send(websocket, {"type": "assistant_text", "text": "Р›РѕРєР°Р»СЊРЅС‹Р№ LLM СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ.", "reply_id": reply_id})
            return "Р›РѕРєР°Р»СЊРЅС‹Р№ LLM СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ."
        queue: asyncio.Queue[str | None | BaseException] = asyncio.Queue()
        def worker() -> None:
            try:
                for delta in self.clients.chat_stream(messages): queue.put_nowait(delta)
            except BaseException as exc: queue.put_nowait(exc)
            queue.put_nowait(None)
        asyncio.create_task(asyncio.to_thread(worker))
        while True:
            item = await queue.get()
            if item is None: break
            if isinstance(item, BaseException):
                reply = self.clients.chat(messages)
                await self.send(websocket, {"type": "assistant_chunk", "text": reply, "reply_id": reply_id})
                break
            if self.cancel_event and self.cancel_event.is_set():
                await self.send(websocket, {"type": "cancelled", "reply_id": reply_id})
                return reply
            reply += item
            await self.send(websocket, {"type": "assistant_chunk", "text": reply, "reply_id": reply_id})
            sentence = sentence_buffer.add(item)
            if sentence and self.clients:
                index = len(self.tts_tasks)
                task = asyncio.create_task(self.synthesize(sentence, reply_id, index))
                self.tts_tasks.append((index, task))
                task.add_done_callback(lambda _task, i=index: tts_done.put_nowait((i, _task)))
                self.last_tts_streamed = True
        remaining = sentence_buffer.flush()
        if remaining and self.clients:
            index = len(self.tts_tasks)
            task = asyncio.create_task(self.synthesize(remaining, reply_id, index))
            self.tts_tasks.append((index, task))
            task.add_done_callback(lambda _task, i=index: tts_done.put_nowait((i, _task)))
            self.last_tts_streamed = True
        if self.tts_tasks:
            await asyncio.gather(*(task for _, task in self.tts_tasks), return_exceptions=True)
        await tts_done.put(None)
        if self._tts_dispatcher: await self._tts_dispatcher
        await self.send(websocket, {"type": "assistant_text", "text": reply, "reply_id": reply_id})
        return reply

    async def emit_partial(self, websocket, request_id: int) -> None:
        task = self.partial_tasks.get(request_id)
        if task and not task.done(): return
        chunks = list(self.pcm_chunks.get(request_id, []))
        if not chunks or self.clients is None: return
        path = Path(tempfile.gettempdir()) / f"liya_partial_{request_id}_{int(time.time()*1000)}.wav"
        try:
            import struct
            samples = b"".join(chunks); count = len(samples) // 2
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(32000)
                output.writeframes(struct.pack(f"<{count}h", *struct.unpack(f"<{count}h", samples)))
            text = await asyncio.to_thread(self.clients.transcribe, path)
            if text.strip(): await self.send(websocket, {"type": "partial_transcript", "text": text.strip(), "request_id": request_id, "final": False})
        except (LocalServiceError, OSError): return
        finally: path.unlink(missing_ok=True)

    async def process_audio(self, websocket, event: dict) -> None:
        request_id = int(event.get("request_id", 0))
        self.active_reply = f"reply-{request_id}"
        self.cancel_event = asyncio.Event()
        chunks = self.audio_chunks.pop(request_id, [])
        pcm_chunks = self.pcm_chunks.pop(request_id, [])
        if pcm_chunks and not chunks and self.clients is not None:
            import struct, wave
            path = Path(tempfile.gettempdir()) / f"liya_{request_id}.wav"
            samples = b"".join(pcm_chunks)
            count = len(samples) // 2
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(32000)
                output.writeframes(struct.pack(f"<{count}h", *struct.unpack(f"<{count}h", samples)))
        elif not chunks or self.clients is None:
            await self.send(websocket, {"type": "error", "message": "РђСѓРґРёРѕР·Р°РїСЂРѕСЃ РїСѓСЃС‚ РёР»Рё STT РЅРµРґРѕСЃС‚СѓРїРµРЅ"})
            return
        else:
            suffix = ".webm" if event.get("format") == "webm" else ".wav"
            path = Path(tempfile.gettempdir()) / f"liya_{request_id}{suffix}"
            path.write_bytes(b"".join(chunks))
        try:
            if not self.active_reply: return
            try:
                events = await asyncio.to_thread(lambda: list(self.clients.transcribe_stream(path)))
            except LocalServiceError:
                events = []
            if events:
                for item in events:
                    await self.send(websocket, {"type": "partial_transcript", "text": item["text"], "request_id": request_id, "final": item["final"]})
                text = str(events[-1]["text"])
            else:
                text = await asyncio.to_thread(self.clients.transcribe, path)
            self.active_reply = f"reply-{request_id}"
            self.cancel_event = asyncio.Event()
            await self.set_state(websocket, "thinking")
            await self.send(websocket, {"type": "transcript", "text": text, "final": True})
            self.history.append({"role": "user", "content": text})
            try:
                messages = [{"role": "system", "content": "РўС‹ вЂ” Р›РёСЏ, Р»РѕРєР°Р»СЊРЅС‹Р№ РіРѕР»РѕСЃРѕРІРѕР№ РєРѕРјРїР°РЅСЊРѕРЅ. РћС‚РІРµС‡Р°Р№ С‚РµРїР»Рѕ, РєСЂР°С‚РєРѕ Рё РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ."}] + self.history[-12:]
                await self.set_state(websocket, "speaking")
                reply = await self.stream_reply(websocket, messages, self.active_reply)
            except LocalServiceError:
                reply = "РЇ СѓСЃР»С‹С€Р°Р»Р° С‚РµР±СЏ, РЅРѕ Р»РѕРєР°Р»СЊРЅС‹Р№ LLM СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ."
            self.history.append({"role": "assistant", "content": reply})
            if self.cancel_event and self.cancel_event.is_set():
                return
            if not self.last_tts_streamed:
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
            await self.send(websocket, {"type": "error", "message": "РќРµРєРѕСЂСЂРµРєС‚РЅРѕРµ СЃРѕР±С‹С‚РёРµ"})
            return
        kind = event.get("type")
        if kind == "start_listening":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks[request_id] = []
            self.pcm_chunks[request_id] = []
            self.partial_last_ms[request_id] = time.monotonic() * 1000
            await self.set_state(websocket, "listening")
        elif kind == "audio_chunk":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks.setdefault(request_id, []).append(base64.b64decode(event.get("data", "")))
        elif kind == "audio_pcm_chunk":
            request_id = int(event.get("request_id", 0))
            self.pcm_chunks.setdefault(request_id, []).append(base64.b64decode(event.get("data", "")))
            now = time.monotonic() * 1000
            if now - self.partial_last_ms.get(request_id, now) >= 800:
                self.partial_last_ms[request_id] = now
                self.partial_tasks[request_id] = asyncio.create_task(self.emit_partial(websocket, request_id))
        elif kind == "finish_listening":
            partial = self.partial_tasks.get(int(event.get("request_id", 0)))
            if partial and not partial.done(): partial.cancel()
            self.active_task = asyncio.create_task(self.process_audio(websocket, event))
        elif kind == "text":
            self.active_task = asyncio.create_task(self.process_text(websocket, event))
        elif kind == "cancel":
            if self.cancel_event: self.cancel_event.set()
            for _, task in list(self.tts_tasks):
                if not task.done(): task.cancel()
            if self.active_task and not self.active_task.done(): self.active_task.cancel()
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
            messages = [{"role": "system", "content": "РўС‹ вЂ” Р›РёСЏ, Р»РѕРєР°Р»СЊРЅС‹Р№ РіРѕР»РѕСЃРѕРІРѕР№ РєРѕРјРїР°РЅСЊРѕРЅ. РћС‚РІРµС‡Р°Р№ С‚РµРїР»Рѕ, РєСЂР°С‚РєРѕ Рё РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ."}] + self.history[-12:]
            await self.set_state(websocket, "speaking")
            reply = await self.stream_reply(websocket, messages, self.active_reply or "reply")
        except LocalServiceError:
            reply = "РЇ РїРѕР»СѓС‡РёР»Р° СЃРѕРѕР±С‰РµРЅРёРµ, РЅРѕ Р»РѕРєР°Р»СЊРЅС‹Р№ LLM СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ."
        self.history.append({"role": "assistant", "content": reply})


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    if websockets is None:
        raise RuntimeError("Install the UI extra: pip install 'liya-voice-assistant[ui]'")
    settings = Settings.load(Path("config.json"))
    runtime = LiyaRuntime(LocalClients(settings))
    async with websockets.serve(runtime.handle, host, port):
        print(f"Liya runtime: ws://{host}:{port}")
        await asyncio.Future()

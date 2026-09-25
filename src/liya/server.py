from __future__ import annotations

import asyncio
import base64
import difflib
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
from .stt import LocalHttpSTT, StreamingSTTBackend, select_stt
from .memory_store import MemoryStore


class SentenceBuffer:
    def __init__(self) -> None:
        self.buffer = ""
    def add(self, delta: str) -> str | None:
        self.buffer += delta
        for mark in (".", "!", "?", "РІР‚В¦", "\n"):
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
        self.stt = select_stt(clients, backend=getattr(getattr(clients, "settings", None), "stt_backend", "local_http")) if clients is not None else None
        self.memory = MemoryStore("data/memory.sqlite3")
        self.state = "idle"
        self.history: list[dict[str, str]] = []
        self.audio_chunks: dict[int, list[bytes]] = {}
        self.pcm_chunks: dict[int, list[bytes]] = {}
        self.partial_tasks: dict[int, asyncio.Task] = {}
        self.partial_last_ms: dict[int, float] = {}
        self.partial_calls: dict[int, int] = {}
        self.partial_versions: dict[int, int] = {}
        self.cancel_event: asyncio.Event | None = None
        self.active_reply: str | None = None
        self.active_task: asyncio.Task | None = None
        self.active_turn_id: int | None = None
        self.generation = 0
        self.llm_tasks: list[asyncio.Task] = []
        self.last_tts_streamed = False
        self.tts_tasks: list[tuple[int, asyncio.Task]] = []
        self._tts_dispatcher: asyncio.Task | None = None
        self.preemptive_texts: dict[int, list[str]] = {}
        self.preemptive_tasks: dict[int, asyncio.Task] = {}
        self.preemptive_audio: dict[int, list[bytes]] = {}

    def is_current(self, turn_id: int | None) -> bool:
        return turn_id is not None and turn_id == self.active_turn_id and self.generation == turn_id

    def begin_turn(self, request_id: int) -> int:
        self.generation += 1
        self.active_turn_id = self.generation
        self.active_reply = f"reply-{request_id}-{self.generation}"
        self.cancel_event = asyncio.Event()
        return self.generation

    def cancel_active(self) -> None:
        if self.cancel_event: self.cancel_event.set()
        for task in [*self.tts_tasks, *self.llm_tasks, *self.preemptive_tasks.values()]:
            if not task.done(): task.cancel()
        if self.active_task and not self.active_task.done(): self.active_task.cancel()
        if self._tts_dispatcher and not self._tts_dispatcher.done(): self._tts_dispatcher.cancel()

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


    async def stream_reply(self, websocket, messages: list[dict[str, str]], reply_id: str, turn_id: int) -> str:
        self.last_tts_streamed = False
        self._websocket = websocket
        self.tts_tasks = []
        self._tts_dispatcher = None
        tts_done: asyncio.Queue[tuple[int, asyncio.Task] | None] = asyncio.Queue()
        self._tts_dispatcher = asyncio.create_task(self.dispatch_tts(websocket, reply_id, tts_done))
        reply = ""
        sentence_buffer = SentenceBuffer()
        if not self.clients:
            await self.send(websocket, {"type": "assistant_text", "text": "Р вЂєР С•Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– LLM РЎРѓР ВµР в„–РЎвЂЎР В°РЎРѓ Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р….", "reply_id": reply_id})
            return "Р вЂєР С•Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– LLM РЎРѓР ВµР в„–РЎвЂЎР В°РЎРѓ Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р…."
        queue: asyncio.Queue[str | None | BaseException] = asyncio.Queue()
        def worker() -> None:
            try:
                for delta in self.clients.chat_stream(messages): queue.put_nowait(delta)
            except BaseException as exc: queue.put_nowait(exc)
            queue.put_nowait(None)
        llm_task = asyncio.create_task(asyncio.to_thread(worker))
        self.llm_tasks.append(llm_task)
        while True:
            item = await queue.get()
            if item is None: break
            if isinstance(item, BaseException):
                reply = self.clients.chat(messages)
                await self.send(websocket, {"type": "assistant_chunk", "text": reply, "reply_id": reply_id})
                break
            if self.cancel_event and self.cancel_event.is_set() or not self.is_current(turn_id):
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

    async def emit_partial(self, websocket, request_id: int, version: int) -> None:
        task = self.partial_tasks.get(request_id)
        if task and not task.done(): return
        chunks = list(self.pcm_chunks.get(request_id, []))
        settings = self.clients.settings if self.clients else None
        if not chunks or self.clients is None: return
        if settings:
            max_bytes = max(1, settings.stt_partial_window_seconds * 32000 * 2)
            samples = b"".join(chunks)[-max_bytes:]
        else:
            samples = b"".join(chunks)
        path = Path(tempfile.gettempdir()) / f"liya_partial_{request_id}_{int(time.time()*1000)}.wav"
        try:
            import struct
            count = len(samples) // 2
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1); output.setsampwidth(2); output.setframerate(32000)
                output.writeframes(struct.pack(f"<{count}h", *struct.unpack(f"<{count}h", samples)))
            text, confidence = await asyncio.to_thread(self.stt.transcribe_with_confidence, path)
            threshold = settings.stt_partial_min_confidence if settings else 0.35
            if text.strip() and confidence >= threshold and self.partial_versions.get(request_id) == version:
                self.preemptive_texts.setdefault(request_id, []).append(text.strip())
                if request_id not in self.preemptive_tasks or self.preemptive_tasks[request_id].done():
                    old = self.preemptive_tasks.get(request_id)
                    if old and not old.done(): old.cancel()
                    self.preemptive_tasks[request_id] = asyncio.create_task(self.preemptive_reply(text.strip(), request_id))
                await self.send(websocket, {"type": "partial_transcript", "text": text.strip(), "request_id": request_id, "final": False, "confidence": confidence})
        except (LocalServiceError, OSError): return
        finally: path.unlink(missing_ok=True)

    async def preemptive_reply(self, text: str, request_id: int) -> tuple[str, list[bytes]]:
        if not self.clients: return ""
        prompt = [{"role": "system", "content": "РўС‹ вЂ” Р›РёСЏ. РџРѕРґРіРѕС‚РѕРІСЊ РєСЂР°С‚РєРёР№ С‡РµСЂРЅРѕРІРѕР№ РѕС‚РІРµС‚, РЅРµ РґРѕР±Р°РІР»СЏР№ РІС‹РґСѓРјР°РЅРЅС‹Рµ С„Р°РєС‚С‹."}, {"role": "user", "content": text}]
        draft = await asyncio.to_thread(self.clients.chat, prompt)
        settings = self.clients.settings
        if len(text.strip()) < settings.preemptive_min_chars:
            return draft, []
        chunks = []
        sentences = []
        minimum = settings.preemptive_min_chars if settings else 12
        maximum = settings.preemptive_max_sentences if settings else 4
        buffer = SentenceBuffer()
        for token in draft.split():
            sentence = buffer.add(token)
            if sentence: sentences.append(sentence)
        if buffer.buffer.strip(): sentences.append(buffer.flush() or "")
        sentences = sentences[:settings.preemptive_max_sentences]
        for index, sentence in enumerate(sentences):
            output = Path(tempfile.gettempdir()) / f"liya_preemptive_{request_id}_{index}.wav"
            try:
                audio_path = await asyncio.to_thread(self.clients.speak, sentence, output)
                chunks.append(audio_path.read_bytes())
            finally:
                output.unlink(missing_ok=True)
        return draft, chunks


    async def process_audio(self, websocket, event: dict) -> None:
        request_id = int(event.get("request_id", 0))
        turn_id = self.begin_turn(request_id)
        self.active_reply = f"reply-{request_id}-{turn_id}"
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
            await self.send(websocket, {"type": "error", "message": "Р С’РЎС“Р Т‘Р С‘Р С•Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р С—РЎС“РЎРѓРЎвЂљ Р С‘Р В»Р С‘ STT Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р…"})
            return
        else:
            suffix = ".webm" if event.get("format") == "webm" else ".wav"
            path = Path(tempfile.gettempdir()) / f"liya_{request_id}{suffix}"
            path.write_bytes(b"".join(chunks))
        started = time.perf_counter()
        stt_started = started
        try:
            streaming_stt = bool(getattr(self.clients.capabilities, "stt_stream", False))
            events = await asyncio.to_thread(lambda: list(self.stt.transcribe_stream(path))) if streaming_stt else []
        except LocalServiceError:
            events = []
        stt_ms = int((time.perf_counter() - stt_started) * 1000)
        if events:
            for item in events:
                await self.send(websocket, {"type": "partial_transcript", "text": item["text"], "request_id": request_id, "final": item["final"]})
            text = str(events[-1]["text"])
        else:
            text = await asyncio.to_thread(self.stt.transcribe, path)
        llm_started = time.perf_counter()
        await self.set_state(websocket, "thinking")
        await self.send(websocket, {"type": "transcript", "text": text, "final": True})
        self.history.append({"role": "user", "content": text})
        self.memory.extract(text)
        related = self.memory.search(text)
        memory_context = [{"role": "system", "content": "РР· РґРѕР»РіРѕРІСЂРµРјРµРЅРЅРѕР№ РїР°РјСЏС‚Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: " + "; ".join(fact.content for fact in related)}] if related else []
        draft_task = self.preemptive_tasks.pop(request_id, None)
        draft = ""
        draft_audio = self.preemptive_audio.pop(request_id, [])
        if draft_task and not draft_task.cancelled():
            try:
                draft, draft_audio = await draft_task
            except Exception:
                draft = ""
        previous = self.preemptive_texts.pop(request_id, [])
        similarity = difflib.SequenceMatcher(None, text.casefold(), previous[-1].casefold()).ratio() if previous else 0.0
        preemptive_used = False
        tts_started = time.perf_counter()
        try:
            messages = memory_context + [{"role": "system", "content": "РўС‹ вЂ” Р›РёСЏ, Р»РѕРєР°Р»СЊРЅС‹Р№ РіРѕР»РѕСЃРѕРІРѕР№ РєРѕРјРїР°РЅСЊРѕРЅ. РћС‚РІРµС‡Р°Р№ С‚РµРїР»Рѕ, РєСЂР°С‚РєРѕ Рё РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ."}] + self.history[-12:]
            if draft and similarity >= 0.65:
                reply = draft
                preemptive_used = True
                await self.set_state(websocket, "speaking")
                await self.send(websocket, {"type": "assistant_text", "text": reply, "reply_id": self.active_reply})
                for index, audio in enumerate(draft_audio):
                    await self.send(websocket, {"type": "audio", "data": base64.b64encode(audio).decode(), "mime": "audio/wav", "sampleRate": 22050, "reply_id": self.active_reply, "index": index})
            else:
                await self.set_state(websocket, "speaking")
                reply = await self.stream_reply(websocket, messages, self.active_reply, turn_id)
        except LocalServiceError:
            reply = "Р›РѕРєР°Р»СЊРЅС‹Р№ LLM СЃРµР№С‡Р°СЃ РЅРµРґРѕСЃС‚СѓРїРµРЅ."
        llm_ms = int((time.perf_counter() - llm_started) * 1000)
        self.history.append({"role": "assistant", "content": reply})
        if self.cancel_event and self.cancel_event.is_set():
            return
        tts_ms = int((time.perf_counter() - tts_started) * 1000)
        if not self.last_tts_streamed:
            output = path.with_name(f"liya_reply_{request_id}.wav")
            audio = await asyncio.to_thread(self.clients.speak, reply, output)
            await self.send(websocket, {"type": "audio", "data": base64.b64encode(audio.read_bytes()).decode(), "mime": "audio/wav", "sampleRate": 22050, "reply_id": self.active_reply})
        total_ms = int((time.perf_counter() - started) * 1000)
        await self.send(websocket, {"type": "pipeline_metrics", "stt_ms": stt_ms, "llm_ms": llm_ms, "tts_ms": tts_ms, "total_ms": total_ms, "preemptive_used": preemptive_used})
        await self.set_state(websocket, "idle")
        path.unlink(missing_ok=True)

    async def handle(self, websocket, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(websocket, {"type": "error", "message": "Р СњР ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•Р Вµ РЎРѓР С•Р В±РЎвЂ№РЎвЂљР С‘Р Вµ"})
            return
        kind = event.get("type")
        if kind == "start_listening":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks[request_id] = []
            self.pcm_chunks[request_id] = []
            self.partial_last_ms[request_id] = time.monotonic() * 1000
            self.partial_calls[request_id] = 0
            self.partial_versions[request_id] = 0
            self.preemptive_texts[request_id] = []
            await self.set_state(websocket, "listening")
        elif kind == "audio_chunk":
            request_id = int(event.get("request_id", 0))
            self.audio_chunks.setdefault(request_id, []).append(base64.b64decode(event.get("data", "")))
        elif kind == "audio_pcm_chunk":
            request_id = int(event.get("request_id", 0))
            self.pcm_chunks.setdefault(request_id, []).append(base64.b64decode(event.get("data", "")))
            now = time.monotonic() * 1000
            settings = self.clients.settings if self.clients else None
            interval = settings.stt_partial_interval_ms if settings else 800
            minimum = settings.stt_partial_min_bytes if settings else 32000
            maximum = settings.stt_partial_max_calls if settings else 6
            total_bytes = sum(len(chunk) for chunk in self.pcm_chunks[request_id])
            if (total_bytes >= minimum and self.partial_calls.get(request_id, 0) < maximum
                    and now - self.partial_last_ms.get(request_id, now) >= interval):
                self.partial_versions[request_id] = self.partial_versions.get(request_id, 0) + 1
                self.partial_last_ms[request_id] = now
                self.partial_calls[request_id] = self.partial_calls.get(request_id, 0) + 1
                self.partial_tasks[request_id] = asyncio.create_task(self.emit_partial(websocket, request_id, self.partial_versions[request_id]))
        elif kind == "finish_listening":
            partial = self.partial_tasks.get(int(event.get("request_id", 0)))
            if partial and not partial.done(): partial.cancel()
            self.active_task = asyncio.create_task(self.process_audio(websocket, event))
        elif kind == "text":
            self.active_task = asyncio.create_task(self.process_text(websocket, event))
        elif kind == "cancel":
            self.cancel_active()
            if self.active_reply: await self.send(websocket, {"type": "cancelled", "reply_id": self.active_reply})
            await self.set_state(websocket, "idle")
        elif kind == "memory_list":
            await self.send(websocket, {"type": "memory", "facts": [{"id": fact.id, "kind": fact.kind, "content": fact.content, "source": fact.source} for fact in self.memory.list()]})
        elif kind == "memory_delete":
            removed = self.memory.delete(int(event.get("id", 0)))
            await self.send(websocket, {"type": "memory", "deleted": removed})
        elif kind == "ping":
            await self.send(websocket, {"type": "pong"})

    async def process_text(self, websocket, event: dict) -> None:
        text = str(event.get("text", "")).strip()
        if not text:
            return
        turn_id = self.begin_turn(int(time.time_ns()))
        self.active_reply = f"reply-{turn_id}"
        await self.set_state(websocket, "thinking")
        await self.send(websocket, {"type": "transcript", "text": text, "final": True})
        self.history.append({"role": "user", "content": text})
        self.memory.extract(text)
        related = self.memory.search(text)
        memory_context = [{"role": "system", "content": "РР· РґРѕР»РіРѕРІСЂРµРјРµРЅРЅРѕР№ РїР°РјСЏС‚Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ: " + "; ".join(fact.content for fact in related)}] if related else []
        try:
            if self.clients is None:
                raise LocalServiceError("LLM client is not configured")
            messages = memory_context + [{"role": "system", "content": "Ты — Лия, локальный голосовой компаньон. Отвечай тепло, кратко и естественно."}] + self.history[-12:]
            await self.set_state(websocket, "speaking")
            reply = await self.stream_reply(websocket, messages, self.active_reply or "reply", self.active_turn_id or 0)
        except LocalServiceError:
            reply = "Р Р‡ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘Р В»Р В° РЎРѓР С•Р С•Р В±РЎвЂ°Р ВµР Р…Р С‘Р Вµ, Р Р…Р С• Р В»Р С•Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– LLM РЎРѓР ВµР в„–РЎвЂЎР В°РЎРѓ Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р…."
        self.history.append({"role": "assistant", "content": reply})


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    if websockets is None:
        raise RuntimeError("Install the UI extra: pip install 'liya-voice-assistant[ui]'")
    settings = Settings.load(Path("config.json"))
    runtime = LiyaRuntime(LocalClients(settings))
    async with websockets.serve(runtime.handle, host, port):
        print(f"Liya runtime: ws://{host}:{port}")
        await asyncio.Future()

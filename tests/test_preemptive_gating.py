import asyncio
import base64
import json
from pathlib import Path

from liya.clients import LocalClients
from liya.config import Settings
from liya.server import LiyaRuntime


class Socket:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)


class GatingClients(LocalClients):
    def __init__(self, settings, texts):
        super().__init__(settings)
        self.texts = list(texts)
        self.chat_calls = 0

    def transcribe_with_confidence(self, path):
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return text, 0.9

    def transcribe(self, path):
        return self.texts[0]

    def chat(self, messages):
        self.chat_calls += 1
        return "Черновик"

    def speak(self, text, output_path=None):
        path = Path(output_path or "out.wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return path


def _settings(**overrides):
    base = dict(stt_partial_min_bytes=2, stt_partial_interval_ms=0, stt_partial_max_calls=3, stt_partial_min_confidence=0.3)
    base.update(overrides)
    return Settings("l", "s", "t", "m", "ru", "v", 2, "out.wav", **base)


def _patch_spawn(runtime):
    spawned = []

    async def fake_preemptive(text, request_id):
        spawned.append(text)
        return "", []

    runtime.preemptive_reply = fake_preemptive
    return spawned


async def _partial(runtime, ws, request_id):
    await runtime.handle(ws, json.dumps({"type": "audio_pcm_chunk", "request_id": request_id, "data": base64.b64encode(b"12").decode()}))
    await runtime.partial_tasks[request_id]
    task = runtime.preemptive_tasks.get(request_id)
    if task is not None:
        await task


def test_short_interim_does_not_spawn_draft():
    async def run():
        runtime = LiyaRuntime(GatingClients(_settings(), ["привет"]))
        spawned = _patch_spawn(runtime)
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 1}))
        await _partial(runtime, ws, 1)

        assert spawned == []
        assert 1 not in runtime.preemptive_tasks
        interim = [json.loads(event) for event in ws.events if "interim_transcript" in event]
        assert interim and interim[0]["text"] == "привет"
    asyncio.run(run())


def test_unstable_interim_does_not_spawn_draft():
    async def run():
        texts = ["который час сейчас в москве", "я хочу заказать пиццу с сыром"]
        runtime = LiyaRuntime(GatingClients(_settings(), texts))
        spawned = _patch_spawn(runtime)
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 2}))
        await _partial(runtime, ws, 2)
        assert len(spawned) == 1

        await _partial(runtime, ws, 2)
        assert len(spawned) == 1
        assert len(runtime.preemptive_texts[2]) == 2
    asyncio.run(run())


def test_stable_interim_spawns_new_draft():
    async def run():
        texts = ["который час сейчас в москве", "который час сейчас в москве по времени"]
        runtime = LiyaRuntime(GatingClients(_settings(), texts))
        spawned = _patch_spawn(runtime)
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 3}))
        await _partial(runtime, ws, 3)
        assert len(spawned) == 1

        await _partial(runtime, ws, 3)
        assert len(spawned) == 2
    asyncio.run(run())


def test_short_text_never_calls_chat():
    async def run():
        clients = GatingClients(_settings(), ["привет"])
        runtime = LiyaRuntime(clients)
        draft, audio = await runtime.preemptive_reply("привет", 1)
        assert (draft, audio) == ("", [])
        assert clients.chat_calls == 0
    asyncio.run(run())
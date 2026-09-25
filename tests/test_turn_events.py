import asyncio
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


class SmokeClients(LocalClients):
    def transcribe_with_confidence(self, path):
        return "Привет", 1.0

    def transcribe(self, path):
        return "Привет"

    def transcribe_stream(self, path):
        raise AssertionError("batch runtime must not call streaming STT")

    def chat(self, messages):
        return "Здравствуй"

    def speak(self, text, output_path=None):
        path = Path(output_path or "out.wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return path


def _events(ws):
    return [json.loads(item) for item in ws.events]


def test_audio_flow_events_carry_turn_stamp():
    async def run():
        settings = Settings("l", "s", "t", "m", "ru", "v", 2, "out.wav")
        runtime = LiyaRuntime(SmokeClients(settings))
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 91}))
        runtime.pcm_chunks[91] = [b"\x00\x00" * 16000]
        await runtime.handle(ws, json.dumps({"type": "finish_listening", "request_id": 91, "format": "pcm"}))
        await runtime.active_task

        events = _events(ws)
        assert all("turn_id" in event and "generation" in event for event in events)

        listening = next(event for event in events if event["type"] == "state" and event["state"] == "listening")
        assert listening["turn_id"] is None
        assert listening["generation"] == 0

        scoped = [event for event in events if event["type"] in ("transcript", "assistant_chunk", "assistant_text", "audio", "pipeline_metrics")]
        assert scoped
        assert all(event["turn_id"] == 1 and event["generation"] == 1 for event in scoped)

        states = [event for event in events if event["type"] == "state" and event["state"] in ("thinking", "speaking", "idle")]
        assert states
        assert all(event["turn_id"] == 1 and event["generation"] == 1 for event in states)
    asyncio.run(run())


def test_text_flow_stamps_reply_events():
    async def run():
        settings = Settings("l", "s", "t", "m", "ru", "v", 2, "out.wav")
        runtime = LiyaRuntime(SmokeClients(settings))
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "text", "text": "привет"}))
        await runtime.active_task

        events = _events(ws)
        scoped = [event for event in events if event["type"] in ("transcript", "assistant_chunk", "assistant_text", "audio")]
        assert scoped
        assert all(event["turn_id"] == 1 and event["generation"] == 1 for event in scoped)
    asyncio.run(run())


def test_explicit_turn_stamp_survives_new_turn():
    async def run():
        runtime = LiyaRuntime(None)
        ws = Socket()
        first = runtime.begin_turn(1)
        second = runtime.begin_turn(2)

        await runtime.send(ws, {"type": "stale", "turn_id": first, "generation": first})
        stale = _events(ws)[-1]
        assert stale["turn_id"] == first
        assert stale["generation"] == first

        await runtime.send(ws, {"type": "stale2"}, turn_id=first)
        stale = _events(ws)[-1]
        assert stale["turn_id"] == first
        assert stale["generation"] == first

        await runtime.send(ws, {"type": "current"})
        current = _events(ws)[-1]
        assert current["turn_id"] == second
        assert current["generation"] == second
    asyncio.run(run())
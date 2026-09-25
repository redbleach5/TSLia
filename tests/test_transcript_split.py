import asyncio
import base64
import json
from pathlib import Path

from liya.clients import LocalClients, ServiceCapabilities
from liya.config import Settings
from liya.server import LiyaRuntime


class Socket:
    def __init__(self):
        self.events = []

    async def send(self, event):
        self.events.append(event)


class SplitClients(LocalClients):
    def __init__(self, settings, text="Привет", confidence=0.9):
        super().__init__(settings)
        self.text = text
        self.confidence = confidence

    def transcribe_with_confidence(self, path):
        return self.text, self.confidence

    def transcribe(self, path):
        return self.text

    def chat(self, messages):
        return "Ответ"

    def speak(self, text, output_path=None):
        path = Path(output_path or "out.wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return path


class StreamClients(SplitClients):
    def transcribe_stream(self, path):
        yield {"text": "Привет", "final": False}
        yield {"text": "Привет, я Лия", "final": True}


def _settings(**overrides):
    base = dict(stt_partial_min_bytes=2, stt_partial_interval_ms=0, stt_partial_max_calls=2, stt_partial_min_confidence=0.3)
    base.update(overrides)
    return Settings("l", "s", "t", "m", "ru", "v", 2, "out.wav", **base)


def _events(ws):
    return [json.loads(item) for item in ws.events]


def test_interim_is_volatile_and_final_is_committed():
    async def run():
        runtime = LiyaRuntime(SplitClients(_settings()))
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 77}))
        await runtime.handle(ws, json.dumps({"type": "audio_pcm_chunk", "request_id": 77, "data": base64.b64encode(b"12").decode()}))
        await runtime.partial_tasks[77]

        interim = [event for event in _events(ws) if event["type"] == "interim_transcript"]
        assert interim and interim[0]["text"] == "Привет"
        assert interim[0].get("final") is not True

        await runtime.handle(ws, json.dumps({"type": "finish_listening", "request_id": 77, "format": "pcm"}))
        await runtime.active_task

        events = _events(ws)
        final = [event for event in events if event["type"] == "transcript"]
        assert len(final) == 1
        assert final[0]["text"] == "Привет"
        assert final[0]["final"] is True
        assert not any("partial_transcript" in event for event in ws.events)
    asyncio.run(run())


def test_streaming_final_goes_only_through_transcript():
    async def run():
        clients = StreamClients(_settings())
        clients.capabilities = ServiceCapabilities(llm_stream=True, stt_stream=True, tts_stream=False)
        runtime = LiyaRuntime(clients)
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 78}))
        runtime.pcm_chunks[78] = [b"\x00\x00"]
        await runtime.handle(ws, json.dumps({"type": "finish_listening", "request_id": 78, "format": "pcm"}))
        await runtime.active_task

        events = _events(ws)
        interim = [event for event in events if event["type"] == "interim_transcript"]
        assert [event["text"] for event in interim] == ["Привет"]
        final = [event for event in events if event["type"] == "transcript"]
        assert len(final) == 1
        assert final[0]["text"] == "Привет, я Лия"
        assert final[0]["final"] is True
        assert not any(event["type"] == "interim_transcript" and event.get("final") for event in events)
    asyncio.run(run())


def test_cancel_drops_pending_interim_and_always_replies_cancelled():
    async def run():
        import time

        class SlowClients(SplitClients):
            def transcribe_with_confidence(self, path):
                time.sleep(0.3)
                return "зависит от исхода", 0.9

        runtime = LiyaRuntime(SlowClients(_settings()))
        ws = Socket()
        await runtime.handle(ws, json.dumps({"type": "start_listening", "request_id": 88}))
        await runtime.handle(ws, json.dumps({"type": "audio_pcm_chunk", "request_id": 88, "data": base64.b64encode(b"12").decode()}))
        task = runtime.partial_tasks[88]
        assert not task.done()

        await runtime.handle(ws, json.dumps({"type": "cancel"}))
        assert task.cancelling() > 0

        events = _events(ws)
        cancelled = [event for event in events if event["type"] == "cancelled"]
        assert cancelled
        assert events[-1]["type"] == "state" and events[-1]["state"] == "idle"
        await asyncio.sleep(0)
    asyncio.run(run())
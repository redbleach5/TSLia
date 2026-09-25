import asyncio, base64, json
from pathlib import Path
from liya.clients import LocalClients
from liya.config import Settings
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

class FakeClients(LocalClients):
    def transcribe_with_confidence(self,path): return 'тест', 1.0
    def transcribe(self,path): return 'тест'
    def chat(self,messages): return 'Ок'
    def speak(self,text,output_path=None):
        path=Path(output_path or 'o.wav'); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'RIFF'); return path

LOUD = base64.b64encode(b'\xff\x7f' * 16).decode()
QUIET = base64.b64encode(b'\x00\x00' * 16).decode()

def _events(ws):
    return [json.loads(item) for item in ws.events]

async def _send_chunk(runtime, ws, request_id, data):
    await runtime.handle(ws, json.dumps({'type':'audio_pcm_chunk','request_id':request_id,'data':data}))

def test_vad_endpointing_finishes_after_silence():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',
                          vad_endpointing=True, vad_min_silence_ms=100, vad_min_speech_ms=0)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws, json.dumps({'type':'start_listening','request_id':74}))
        session = runtime.vad_sessions[74]
        clock = {'ms': 0.0}
        session.clock = lambda: clock['ms'] / 1000.0
        session.origin_ms = 0.0
        await _send_chunk(runtime, ws, 74, LOUD)
        clock['ms'] = 50
        await _send_chunk(runtime, ws, 74, LOUD)
        clock['ms'] = 60
        await _send_chunk(runtime, ws, 74, QUIET)
        assert not any(event.get('type') == 'endpoint' for event in _events(ws))
        clock['ms'] = 200
        await _send_chunk(runtime, ws, 74, QUIET)
        assert any(event.get('type') == 'endpoint' for event in _events(ws))
        task = runtime.active_task
        assert task is not None and 74 in runtime.vad_finished
        # поздний ручной finish не создаёт вторую обработку
        await runtime.handle(ws, json.dumps({'type':'finish_listening','request_id':74,'format':'pcm'}))
        assert runtime.active_task is task
        await task
        assert any(event.get('type') == 'transcript' for event in _events(ws))
        assert any(event.get('type') == 'pipeline_metrics' for event in _events(ws))
    asyncio.run(run())

def test_vad_endpointing_can_be_disabled():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',
                          vad_endpointing=False, vad_min_silence_ms=100, vad_min_speech_ms=0)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws, json.dumps({'type':'start_listening','request_id':75}))
        session = runtime.vad_sessions[75]
        clock = {'ms': 0.0}
        session.clock = lambda: clock['ms'] / 1000.0
        session.origin_ms = 0.0
        await _send_chunk(runtime, ws, 75, LOUD)
        clock['ms'] = 200
        await _send_chunk(runtime, ws, 75, QUIET)
        assert not any(event.get('type') == 'endpoint' for event in _events(ws))
        assert runtime.active_task is None
        assert 75 not in runtime.vad_finished
        # ручной finish по-прежнему работает
        runtime.pcm_chunks[75] = [b'\xff\x7f' * 16]
        await runtime.handle(ws, json.dumps({'type':'finish_listening','request_id':75,'format':'pcm'}))
        task = runtime.active_task
        assert task is not None
        await task
        assert any(event.get('type') == 'transcript' for event in _events(ws))
    asyncio.run(run())

def test_vad_endpointing_requires_min_speech():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',
                          vad_endpointing=True, vad_min_silence_ms=100, vad_min_speech_ms=100000)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws, json.dumps({'type':'start_listening','request_id':76}))
        session = runtime.vad_sessions[76]
        clock = {'ms': 0.0}
        session.clock = lambda: clock['ms'] / 1000.0
        session.origin_ms = 0.0
        await _send_chunk(runtime, ws, 76, LOUD)
        clock['ms'] = 200
        await _send_chunk(runtime, ws, 76, QUIET)
        # endpointing состоялся (ended), но речь короче vad_min_speech_ms
        assert not any(event.get('type') == 'endpoint' for event in _events(ws))
        assert runtime.active_task is None
        assert 76 not in runtime.vad_finished
    asyncio.run(run())

def test_late_chunks_after_finish_are_ignored():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',stt_partial_min_bytes=1)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws, json.dumps({'type':'start_listening','request_id':77}))
        runtime.pcm_chunks[77] = [b'\xff\x7f' * 16]
        await runtime.handle(ws, json.dumps({'type':'finish_listening','request_id':77,'format':'pcm'}))
        await runtime.active_task
        before = len(runtime.pcm_chunks.get(77, []))
        await _send_chunk(runtime, ws, 77, LOUD)
        assert len(runtime.pcm_chunks.get(77, [])) == before
        assert len(_events(ws)) >= 0
    asyncio.run(run())
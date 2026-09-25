import asyncio, base64, json
from liya.clients import LocalClients
from liya.config import Settings
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

class FakeClients(LocalClients):
    def transcribe_with_confidence(self,path): return 'шум', 0.1

def test_low_confidence_partial_is_not_emitted():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',stt_partial_min_bytes=2,stt_partial_interval_ms=0,stt_partial_max_calls=1,stt_partial_min_confidence=.5)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws,json.dumps({'type':'start_listening','request_id':31}))
        await runtime.handle(ws,json.dumps({'type':'audio_pcm_chunk','request_id':31,'data':base64.b64encode(b'12').decode()}))
        await runtime.partial_tasks[31]
        assert not any('interim_transcript' in event for event in ws.events)
    asyncio.run(run())
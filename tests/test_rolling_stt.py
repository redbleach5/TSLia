import asyncio, base64, json
from liya.clients import LocalClients
from liya.config import Settings
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

class FakeClients(LocalClients):
    def transcribe(self,path): return 'interim'

def test_rolling_partial_is_bounded_by_config():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav',stt_partial_min_bytes=4,stt_partial_interval_ms=0,stt_partial_max_calls=2,stt_partial_window_seconds=1)
        runtime=LiyaRuntime(FakeClients(settings)); ws=Socket()
        await runtime.handle(ws,json.dumps({'type':'start_listening','request_id':21}))
        for _ in range(5): await runtime.handle(ws,json.dumps({'type':'audio_pcm_chunk','request_id':21,'data':base64.b64encode(b'1234').decode()}))
        assert runtime.partial_calls[21] <= 2
    asyncio.run(run())
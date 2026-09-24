import base64
import json
import asyncio
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self, event): self.events.append(event)

def test_audio_protocol_stores_chunks():
    asyncio.run(_test_audio_protocol_stores_chunks())

async def _test_audio_protocol_stores_chunks():
    runtime=LiyaRuntime(None); ws=Socket()
    await runtime.handle(ws,json.dumps({'type':'start_listening','request_id':7}))
    payload=base64.b64encode(b'audio').decode()
    await runtime.handle(ws,json.dumps({'type':'audio_chunk','request_id':7,'data':payload}))
    assert runtime.audio_chunks[7] == [b'audio']
    assert json.loads(ws.events[-1]) == {'type':'state','state':'listening'}


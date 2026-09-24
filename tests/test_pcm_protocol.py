import asyncio, base64, json
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

def test_pcm_chunk_protocol():
    async def run():
        runtime=LiyaRuntime(None); ws=Socket()
        await runtime.handle(ws,json.dumps({'type':'start_listening','request_id':11}))
        await runtime.handle(ws,json.dumps({'type':'audio_pcm_chunk','request_id':11,'data':base64.b64encode(b'\x00\x00').decode()}))
        assert runtime.pcm_chunks[11] == [b'\x00\x00']
        assert json.loads(ws.events[-1])['state']=='listening'
    asyncio.run(run())
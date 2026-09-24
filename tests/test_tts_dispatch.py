import asyncio
import json
from liya.server import LiyaRuntime

class Socket:
    def __init__(self): self.events=[]
    async def send(self, event): self.events.append(event)

def test_tts_dispatch_preserves_sentence_order():
    async def run_test():
        runtime=LiyaRuntime(None); socket=Socket(); done=asyncio.Queue()
        async def synth(index, delay):
            await asyncio.sleep(delay); return index, bytes([index])
        tasks=[(0,asyncio.create_task(synth(0,.02))),(1,asyncio.create_task(synth(1,.001)))]; runtime.tts_tasks=tasks
        dispatcher=asyncio.create_task(runtime.dispatch_tts(socket,'reply',done))
        for item in tasks: done.put_nowait(item)
        done.put_nowait(None); await dispatcher
        audio=[json.loads(event) for event in socket.events]
        assert [item['index'] for item in audio] == [0,1]
    asyncio.run(run_test())
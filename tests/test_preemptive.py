import asyncio
from liya.server import LiyaRuntime
from liya.clients import LocalClients
from liya.config import Settings

class FakeClients(LocalClients):
    def chat(self,messages): return 'черновик'

def test_preemptive_draft_is_available():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav')
        runtime=LiyaRuntime(FakeClients(settings))
        result=await runtime.preemptive_reply('проверка')
        assert result == 'черновик'
    asyncio.run(run())
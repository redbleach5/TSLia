import asyncio
from liya.server import LiyaRuntime
from liya.clients import LocalClients
from liya.config import Settings

class FakeClients(LocalClients):
    def chat(self,messages): return 'черновик.'
    def speak(self,text,output_path=None):
        from pathlib import Path
        path=Path(output_path or 'out.wav'); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'RIFF'); return path

def test_preemptive_draft_is_available():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'o.wav')
        runtime=LiyaRuntime(FakeClients(settings))
        result, audio = await runtime.preemptive_reply('проверка', 1)
        assert result == 'черновик.'
        assert len(audio) == 1
    asyncio.run(run())
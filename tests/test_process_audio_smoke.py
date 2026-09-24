import asyncio, json
from pathlib import Path
from liya.server import LiyaRuntime
from liya.clients import LocalClients
from liya.config import Settings

class Socket:
    def __init__(self): self.events=[]
    async def send(self,event): self.events.append(event)

class SmokeClients(LocalClients):
    def transcribe_with_confidence(self,path): return 'Привет', 1.0
    def transcribe(self,path): return 'Привет'
    def transcribe_stream(self,path): return iter(())
    def chat(self,messages): return 'Здравствуй'
    def speak(self,text,output_path=None):
        path=Path(output_path or 'out.wav'); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'RIFF'); return path

def test_process_audio_reaches_llm():
    async def run():
        settings=Settings('l','s','t','m','ru','v',2,'out.wav'); runtime=LiyaRuntime(SmokeClients(settings)); ws=Socket()
        event={'type':'finish_listening','request_id':5,'format':'pcm'}; runtime.pcm_chunks[5]=[b'\x00\x00'*16000]
        await runtime.process_audio(ws,event)
        assert any(json.loads(item).get('type')=='transcript' for item in ws.events)
        assert any(json.loads(item).get('type')=='assistant_text' for item in ws.events)
    asyncio.run(run())
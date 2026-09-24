from pathlib import Path
from liya.voice import VoicePipeline

class FakeClients:
    def __init__(self): self.calls = []
    def transcribe(self, path): self.calls.append(('stt', str(path))); return 'привет'
    def chat(self, messages): self.calls.append(('llm', messages)); return 'Здравствуй'
    def speak(self, text, output_path=None): self.calls.append(('tts', text)); return Path('out.wav')

def test_pipeline_runs_file():
    clients = FakeClients(); pipeline = VoicePipeline(clients)
    pipeline.submit('input.wav'); pipeline._jobs.join(); pipeline.close()
    assert [call[0] for call in clients.calls] == ['stt', 'llm', 'tts']
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from liya.clients import LocalClients, ServiceCapabilities
from liya.config import Settings


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = 'data: {"choices":[{"delta":{"content":"Привет"}}]}\n\ndata: {"choices":[{"delta":{"content":" от Лии"}}]}\n\ndata: [DONE]\n\n'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_args): pass


def test_chat_stream_parses_sse():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = Settings(f"http://127.0.0.1:{server.server_port}", "s", "t", "m", "ru", "v", 2, "out.wav")
    assert list(LocalClients(settings).chat_stream([])) == ["Привет", " от Лии"]
    server.shutdown()


def test_tts_payload_supports_mlx_model_and_voice_reference(monkeypatch, tmp_path):
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:2', 'http://127.0.0.1:3', 'm', 'ru', 'v', 2, tmp_path / 'out.wav', tts_backend='mlx_audio', tts_model='chatterbox', voice_reference_path='voice.wav', mlx_audio_url='http://127.0.0.1:9')
    clients = LocalClients(settings)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'RIFF'
    monkeypatch.setattr('liya.clients.urllib.request.urlopen', lambda *_args, **_kwargs: Response())
    assert clients.speak('Привет', tmp_path / 'out.wav').read_bytes() == b'RIFF'
    assert clients.last_tts_payload['model'] == 'chatterbox'
    assert clients.last_tts_payload['reference_audio'] == 'voice.wav'


def test_stt_payload_includes_mlx_model(monkeypatch, tmp_path):
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:2', 'http://127.0.0.1:3', 'm', 'ru', 'v', 2, tmp_path / 'out.wav', stt_backend='mlx_audio', stt_model='whisper-large-v3-turbo', mlx_audio_url='http://127.0.0.1:9')
    audio = tmp_path / 'input.wav'; audio.write_bytes(b'RIFF')
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'{"text": "ok"}'
    def open_url(request, **_kwargs): captured['body'] = request.data; captured['url'] = request.full_url; return Response()
    monkeypatch.setattr('liya.clients.urllib.request.urlopen', open_url)
    assert LocalClients(settings).transcribe(audio) == 'ok'
    assert b'name="model"' in captured['body'] and b'whisper-large-v3-turbo' in captured['body']
    assert captured['url'] == 'http://127.0.0.1:9/v1/audio/transcriptions'


def test_capabilities_default_to_honest_modes():
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:2', 'http://127.0.0.1:3', 'm', 'ru', 'v', 2, 'out.wav')
    assert LocalClients(settings).capabilities == ServiceCapabilities(llm_stream=True, stt_stream=False, tts_stream=False)

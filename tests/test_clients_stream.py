import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from liya.clients import LocalClients
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
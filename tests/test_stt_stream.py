import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from liya.clients import LocalClients
from liya.config import Settings

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        body='data: {"text":"Привет"}\n\ndata: {"text":"Привет, я Лия","final":true}\n\ndata: [DONE]\n\n'.encode()
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass

def test_stt_stream_parses_interim_events(tmp_path):
    server=HTTPServer(('127.0.0.1',0),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
    audio=tmp_path/'sample.webm'; audio.write_bytes(b'audio')
    settings=Settings('l',f'http://127.0.0.1:{server.server_port}','t','m','ru','v',2,tmp_path/'out.wav')
    events=list(LocalClients(settings).transcribe_stream(audio))
    assert events == [{'text':'Привет','final':False},{'text':'Привет, я Лия','final':True}]
    server.shutdown()
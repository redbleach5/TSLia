import asyncio
import contextlib
import http.server
import socket
import threading

from liya.face import (
    A2F_DEFAULT_HEALTH_URL,
    A2F_DEFAULT_URL,
    ARKIT_BLENDSHAPES,
    Audio2FaceBackend,
    NullFaceBackend,
    describe_face_backend,
    frame_from_weights,
    http_health_ok,
    normalize_weights,
    select_face_backend,
)


def test_arkit_list_is_canonical():
    assert len(ARKIT_BLENDSHAPES) == 52
    assert len(set(ARKIT_BLENDSHAPES)) == 52
    assert "JawOpen" in ARKIT_BLENDSHAPES and "MouthClose" in ARKIT_BLENDSHAPES
    assert all(name[:1].isupper() for name in ARKIT_BLENDSHAPES)


def test_normalize_weights_clamps_and_drops_zeros():
    weights = normalize_weights({"JawOpen": 1.4, "MouthSmileLeft": -0.2, "EyeBlinkLeft": "0.5", "bad": "нет"})
    assert weights == {"JawOpen": 1.0, "EyeBlinkLeft": 0.5}


def test_frame_event_rounds_and_keeps_names():
    frame = frame_from_weights({"JawOpen": 0.123456, "NoseSneerLeft": 0.7, "MouthClose": 0.0}, time_code=1.234567)
    event = frame.as_event()
    assert event["type"] == "face_frame"
    assert event["time_code"] == 1.2346
    assert event["weights"] == {"JawOpen": 0.1235, "NoseSneerLeft": 0.7}


class _Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - интерфейс BaseHTTPRequestHandler
        if self.path == "/v1/health/ready":
            body = b'{"status":"ready"}'
        else:
            body = b"nope"
        self.send_response(200 if self.path == "/v1/health/ready" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # тишина в выводе тестов
        pass


@contextlib.contextmanager
def _health_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1/health/ready"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _closed_port_url() -> str:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1/health/ready"


def test_health_probe_reads_documented_endpoint():
    with _health_server() as url:
        assert http_health_ok(url, timeout=2) is True
        assert http_health_ok(f"{url}/missing", timeout=2) is False
    assert http_health_ok(_closed_port_url(), timeout=0.5) is False


def test_a2f_backend_reports_missing_grpc_client():
    backend = Audio2FaceBackend(grpc_available=lambda: False, health_probe=lambda: True)
    reason = backend.unavailable_reason()
    assert reason is not None and "grpcio" in reason and A2F_DEFAULT_URL in reason
    assert backend.health() is True


def test_a2f_backend_reports_dead_service_when_client_ready():
    backend = Audio2FaceBackend(grpc_available=lambda: True, health_probe=lambda: False)
    reason = backend.unavailable_reason()
    assert reason is not None and A2F_DEFAULT_HEALTH_URL in reason


def test_a2f_backend_available_only_when_both_conditions_hold():
    backend = Audio2FaceBackend(grpc_available=lambda: True, health_probe=lambda: True)
    assert backend.unavailable_reason() is None
    assert backend.name == "audio2face"


def test_a2f_frames_never_fake_data():
    unavailable = Audio2FaceBackend(grpc_available=lambda: False, health_probe=lambda: False)
    assert asyncio.run(unavailable.frames(b"\x00" * 16)) == []
    ready = Audio2FaceBackend(grpc_available=lambda: True, health_probe=lambda: True)
    try:
        asyncio.run(ready.frames(b"\x00" * 16))
    except NotImplementedError as exc:
        assert "ProcessAudioStream" in str(exc)
    else:
        raise AssertionError("доступный бэкенд обязан дойти до NotImplementedError, а не врать кадрами")


def test_null_backend_never_claims_frames():
    backend = NullFaceBackend()
    assert backend.name == "ui" and backend.streamed is False
    assert backend.unavailable_reason() is not None
    assert asyncio.run(backend.frames(b"\x00" * 16)) == []


def test_select_face_backend_by_settings():
    assert select_face_backend(None).name == "ui"
    assert select_face_backend(type("S", (), {"face_backend": "ui"})()).name == "ui"
    backend = select_face_backend(type("S", (), {"face_backend": "Audio2Face", "a2f_url": "10.0.0.5:52000"})())
    assert backend.name == "audio2face" and backend.url == "10.0.0.5:52000"


def test_describe_face_backend_is_honest():
    ui_line = describe_face_backend(type("S", (), {"face_backend": "ui"})())
    assert "процедурный риг UI" in ui_line
    a2f_line = describe_face_backend(type("S", (), {"face_backend": "audio2face"})())
    assert "audio2face" in a2f_line and "недоступен" in a2f_line

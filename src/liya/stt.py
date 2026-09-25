class STTBackend:
    def transcribe(self, audio_path: str | Path) -> str:
        raise NotImplementedError
    def transcribe_with_confidence(self, audio_path: str | Path) -> tuple[str, float]:
        return self.transcribe(audio_path), 1.0
    def transcribe_stream(self, audio_path: str | Path):
        raise NotImplementedError

class LocalHttpSTT(STTBackend):
    def __init__(self, clients) -> None:
        self.clients = clients
    def transcribe(self, audio_path): return self.clients.transcribe(audio_path)
    def transcribe_with_confidence(self, audio_path): return self.clients.transcribe_with_confidence(audio_path)
    def transcribe_stream(self, audio_path): return self.clients.transcribe_stream(audio_path)

class StreamingSTTBackend(STTBackend):
    def __init__(self, backend: STTBackend) -> None:
        self.backend = backend
    def transcribe(self, audio_path): return self.backend.transcribe(audio_path)
    def transcribe_with_confidence(self, audio_path): return self.backend.transcribe_with_confidence(audio_path)
    def transcribe_stream(self, audio_path): return self.backend.transcribe_stream(audio_path)

def select_stt(clients, streaming: bool | None = None) -> STTBackend:
    local = LocalHttpSTT(clients)
    enabled = getattr(getattr(clients, "capabilities", None), "stt_stream", False) if streaming is None else streaming
    return StreamingSTTBackend(local) if enabled else local

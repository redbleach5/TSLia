from pathlib import Path
from typing import Protocol, runtime_checkable

@runtime_checkable
class STTBackend(Protocol):
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

class MLXAudioSTT(LocalHttpSTT):
    """MLX-Audio через OpenAI-compatible HTTP endpoint.

    Это transport/backend selection, а не встроенный импорт MLX-Audio: модель
    запускается отдельным локальным MLX-Audio server на Apple Silicon.
    """
    def __init__(self, clients) -> None:
        super().__init__(clients)

class StreamingSTTBackend(STTBackend):
    def __init__(self, backend: STTBackend) -> None:
        self.backend = backend
    def transcribe(self, audio_path): return self.backend.transcribe(audio_path)
    def transcribe_with_confidence(self, audio_path): return self.backend.transcribe_with_confidence(audio_path)
    def transcribe_stream(self, audio_path): return self.backend.transcribe_stream(audio_path)

class MacSpeechAnalyzerSTT(STTBackend):
    """Optional bridge target; the Swift plugin supplies the implementation on macOS."""
    def __init__(self, bridge=None, fallback: STTBackend | None = None) -> None:
        self.bridge = bridge
        self.fallback = fallback
    def transcribe(self, audio_path):
        if self.bridge is None:
            if self.fallback is None: raise RuntimeError("SpeechAnalyzer bridge is unavailable")
            return self.fallback.transcribe(audio_path)
        return self.bridge.transcribe(audio_path)
    def transcribe_with_confidence(self, audio_path):
        if self.bridge is not None: return self.bridge.transcribe_with_confidence(audio_path)
        if self.fallback is None: raise RuntimeError("SpeechAnalyzer bridge is unavailable")
        return self.fallback.transcribe_with_confidence(audio_path)
    def transcribe_stream(self, audio_path):
        if self.bridge is not None: return self.bridge.transcribe_stream(audio_path)
        if self.fallback is None: raise RuntimeError("SpeechAnalyzer bridge is unavailable")
        return self.fallback.transcribe_stream(audio_path)

def select_stt(clients, streaming: bool | None = None, backend: str = "local_http", bridge=None) -> STTBackend:
    local = LocalHttpSTT(clients)
    if backend in {"mlx_audio", "mlx-audio"}: return MLXAudioSTT(clients)
    if backend == "macos_speech": return MacSpeechAnalyzerSTT(bridge=bridge, fallback=local)
    enabled = getattr(getattr(clients, "capabilities", None), "stt_stream", False) if streaming is None else streaming
    return StreamingSTTBackend(local) if enabled else local

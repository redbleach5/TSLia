from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass
class VadResult:
    started: bool
    ended: bool
    duration_ms: int
    peak: float

def pcm_energy(chunk: bytes) -> float:
    """Пиковая амплитуда s16le PCM в диапазоне 0..1; мусор и хвосты < 2 байт игнорируются."""
    count = len(chunk) // 2
    if count == 0:
        return 0.0
    peak = max(abs(int.from_bytes(chunk[i:i + 2], "little", signed=True)) for i in range(0, count * 2, 2))
    return peak / 32768.0

class EnergyVad:
    """Машина endpointing по score 0..1: энергия кадра или вероятность Silero VAD."""
    def __init__(self, threshold: float=0.025, min_speech_ms: int=300, min_silence_ms: int=850, max_seconds: int=30):
        self.threshold=threshold; self.min_speech_ms=min_speech_ms; self.min_silence_ms=min_silence_ms; self.max_seconds=max_seconds
        self.started_at: float|None=None; self.silent_ms=0; self.peak=0.0; self.ended=False; self.last_ms: float|None=None
    def push(self, energy: float, now_ms: float) -> VadResult:
        delta_ms = 0.0 if self.last_ms is None else max(0.0, now_ms - self.last_ms)
        self.last_ms = now_ms
        self.peak=max(self.peak,energy)
        if energy >= self.threshold:
            self.started_at = self.started_at or now_ms; self.silent_ms=0
        elif self.started_at is not None:
            self.silent_ms += delta_ms
        duration=now_ms-(self.started_at or now_ms)
        if self.started_at is not None and self.silent_ms >= self.min_silence_ms: self.ended=True
        if self.started_at is not None and duration >= self.max_seconds*1000: self.ended=True
        return VadResult(self.started_at is not None, self.ended, max(0,duration), self.peak)
    def ready(self) -> bool:
        return self.started_at is not None and not self.ended

class VadSession:
    """Серверная VAD-сессия одного listening request: s16le PCM -> EnergyVad.

    Время считается относительно старта сессии (origin), а не абсолютным
    monotonic, поэтому max_seconds и тишина не зависят от аптайма процесса.
    Часы можно подменить через `clock`/`origin_ms` для детерминированных тестов.

    Источник score подменяем: по умолчанию энергия кадра (`pcm_energy`), при
    `vad_backend = "silero"` — вероятность Silero ONNX. Если Silero недоступен
    или падает в рантайме, сессия прозрачно возвращается к энергетическому
    порогу `fallback_threshold`, а `backend` это показывает.
    """
    def __init__(self, vad: EnergyVad | None = None, clock=..., scorer=None, fallback_threshold: float | None = None):
        self.vad = vad or EnergyVad()
        self.clock = time.monotonic if clock is ... else clock
        self.origin_ms = self.clock() * 1000.0
        self.scorer = scorer
        self.fallback_threshold = self.vad.threshold if fallback_threshold is None else float(fallback_threshold)
        self.using_fallback = False
    @property
    def backend(self) -> str:
        if self.scorer is None:
            return "energy"
        return "energy (fallback)" if self.using_fallback else str(getattr(self.scorer, "backend", "energy"))
    @classmethod
    def from_settings(cls, settings) -> "VadSession":
        if settings is None:
            return cls()
        threshold = float(settings.vad_threshold)
        scorer = None
        backend = str(getattr(settings, "vad_backend", "energy") or "energy").lower()
        if backend == "silero":
            from .silero_vad import load_silero_scorer
            scorer = load_silero_scorer(
                getattr(settings, "vad_model_path", "models/silero_vad.onnx"),
                threshold=float(getattr(settings, "vad_silero_threshold", 0.5)),
            )
            if scorer is not None:
                threshold = float(getattr(settings, "vad_silero_threshold", 0.5))
        return cls(EnergyVad(
            threshold=threshold,
            min_speech_ms=settings.vad_min_speech_ms,
            min_silence_ms=settings.vad_min_silence_ms,
            max_seconds=settings.vad_max_seconds,
        ), scorer=scorer, fallback_threshold=float(settings.vad_threshold))
    def feed_pcm(self, chunk: bytes, now_ms: float | None = None) -> VadResult:
        if now_ms is None:
            now_ms = self.clock() * 1000.0 - self.origin_ms
        score = self.scorer.score(chunk) if self.scorer is not None else pcm_energy(chunk)
        if self.scorer is not None and getattr(self.scorer, "using_fallback", False) and not self.using_fallback:
            # Вероятность Silero больше не приходит: возвращаем энергетический порог.
            self.vad.threshold = self.fallback_threshold
            self.using_fallback = True
        return self.vad.push(score, now_ms)
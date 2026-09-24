from __future__ import annotations
from dataclasses import dataclass

@dataclass
class VadResult:
    started: bool
    ended: bool
    duration_ms: int
    peak: float

class EnergyVad:
    def __init__(self, threshold: float=0.025, min_speech_ms: int=300, min_silence_ms: int=850, max_seconds: int=30):
        self.threshold=threshold; self.min_speech_ms=min_speech_ms; self.min_silence_ms=min_silence_ms; self.max_seconds=max_seconds
        self.started_at: float|None=None; self.silent_ms=0; self.peak=0.0; self.ended=False
    def push(self, energy: float, now_ms: float) -> VadResult:
        self.peak=max(self.peak,energy)
        if energy >= self.threshold:
            self.started_at = self.started_at or now_ms; self.silent_ms=0
        elif self.started_at is not None:
            self.silent_ms += 50
        duration=now_ms-(self.started_at or now_ms)
        if self.started_at is not None and self.silent_ms >= self.min_silence_ms: self.ended=True
        if now_ms >= self.max_seconds*1000: self.ended=True
        return VadResult(self.started_at is not None, self.ended, max(0,duration), self.peak)
    def ready(self) -> bool:
        return self.started_at is not None and not self.ended
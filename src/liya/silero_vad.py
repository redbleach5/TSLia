from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from .vad import pcm_energy

try:
    import numpy as np
except ImportError:
    np = None

MODEL_SAMPLE_RATE = 16000
MODEL_FRAME_SAMPLES = 512
FALLBACK_AFTER_ERRORS = 3
_SESSIONS: dict[str, object] = {}

@dataclass
class SpeechScore:
    is_speech: bool
    confidence: float

class SileroScorer:
    """Silero VAD (ONNX) как scorer для `VadSession`.

    Пайплайн Лии отдаёт s16le PCM 32 kHz, модель обучена на 16 kHz, поэтому
    вход децимируется с усреднением соседних сэмплов, а кадры по 512 сэмплов
    набираются из буфера: неполный кадр ждёт следующего `score`.

    Внутреннее рекуррентное состояние модели (вход/выход `state`) сохраняется
    между кадрами и сбрасывается через `reset()`. Если инференс падает
    `FALLBACK_AFTER_ERRORS` раз подряд, scorer помечает `using_fallback` и
    возвращает энергетическую оценку — вызывающая сторона переключает порог.
    """
    def __init__(self, session, source_rate: int = 32000, threshold: float = 0.5, max_errors: int = FALLBACK_AFTER_ERRORS) -> None:
        self.session = session
        self.source_rate = max(1, int(source_rate))
        self.threshold = float(threshold)
        self.max_errors = max(1, int(max_errors))
        self.factor = max(1, round(self.source_rate / MODEL_SAMPLE_RATE))
        self.frame_bytes = MODEL_FRAME_SAMPLES * self.factor * 2
        self.inputs = {meta.name: meta for meta in session.get_inputs()}
        self.outputs = [meta.name for meta in session.get_outputs()]
        self.audio_input = self._pick_input(("input", "audio", "x"))
        self.rate_input = self._pick_input(("sr", "sample_rate", "rate"))
        self.state_input = self._pick_input(("state", "h", "c", "hn", "cn"))
        self.state_output = self._pick_output(("state", "staten", "state_n", "hn", "cn", "h", "c"))
        self.probability_output = self._pick_output(("output", "prob", "probs", "p"))
        self.state = None
        self.errors = 0
        self.using_fallback = False
        self._pending = b""
        self._confidence = 0.0
    @property
    def backend(self) -> str:
        return "silero"
    def _pick_input(self, names: tuple[str, ...]) -> str | None:
        return next((name for name in self.inputs if name.lower() in names), None)
    def _pick_output(self, names: tuple[str, ...]) -> str | None:
        return next((name for name in self.outputs if name.lower() in names), None)
    def _output_name(self) -> str | None:
        if self.probability_output:
            return self.probability_output
        return next((name for name in self.outputs if name != self.state_output), None)
    def _rate_tensor(self):
        dtype = np.int32 if "int32" in str(self.inputs[self.rate_input].type).lower() else np.int64
        return np.array(MODEL_SAMPLE_RATE, dtype=dtype)
    def _state_tensor(self):
        if self.state is not None:
            return self.state
        shape = tuple(dim if isinstance(dim, int) and dim > 0 else 1 for dim in (self.inputs[self.state_input].shape or ()))
        return np.zeros(shape or (2, 1, 1), dtype=np.float32)
    def _infer(self, frame: bytes) -> float | None:
        if self.audio_input is None:
            return None
        try:
            samples = np.frombuffer(frame, dtype="<i2").astype(np.float32) / 32768.0
            if self.factor > 1:
                usable = len(samples) // self.factor * self.factor
                samples = samples[:usable].reshape(-1, self.factor).mean(axis=1)
            feed = {self.audio_input: samples.reshape(1, -1)}
            if self.rate_input:
                feed[self.rate_input] = self._rate_tensor()
            if self.state_input:
                feed[self.state_input] = self._state_tensor()
            produced = dict(zip(self.outputs, self.session.run(None, feed)))
        except Exception:
            # Контракт модели и onnxruntime не общие исключения Лии: помечаем
            # fallback, чтобы не уронить voice loop одним inference error.
            self.errors += 1
            if self.errors >= self.max_errors:
                self.using_fallback = True
            return None
        self.errors = 0
        if self.state_output and self.state_output in produced:
            self.state = produced[self.state_output]
        name = self._output_name()
        if name is None or name not in produced:
            return None
        return float(np.ravel(produced[name])[0])
    def score(self, chunk: bytes) -> float:
        """Вероятность речи 0..1 для очередного куска PCM.

        Значение — максимум по завершённым кадрам внутри куска: длинный блок
        PCM не должен терять начало речи. Пока кадр не набран, возвращается
        оценка предыдущего кадра. После серии ошибок — энергия вместо вероятности.
        """
        if self.using_fallback or np is None:
            return pcm_energy(chunk)
        self._pending += chunk
        values: list[float] = []
        while len(self._pending) >= self.frame_bytes:
            frame, self._pending = self._pending[:self.frame_bytes], self._pending[self.frame_bytes:]
            value = self._infer(frame)
            if value is not None:
                values.append(value)
        if values:
            self._confidence = values[-1]
            return max(values)
        if self.using_fallback:
            return pcm_energy(chunk)
        return self._confidence
    def detect(self, chunk: bytes) -> SpeechScore:
        confidence = self.score(chunk)
        return SpeechScore(confidence >= self.threshold, confidence)
    def probe(self) -> bool:
        """Прогон одного тихого кадра: проверяет контракт модели вне voice loop."""
        return self._infer(b"\x00\x00" * (self.frame_bytes // 2)) is not None
    def reset(self) -> None:
        self._pending = b""
        self._confidence = 0.0
        self.state = None
        self.errors = 0

def silero_unavailable_reason(model_path: str | Path) -> str | None:
    """`None`, если Silero готов к работе; иначе причина, по которой будет energy fallback.

    Нужна для `liya doctor`: скрытый fallback без объяснения противоречил бы
    принципу «ограничения не прячутся за интерфейсом».
    """
    if np is None:
        return "нет numpy"
    if not Path(model_path).is_file():
        return f"нет файла {model_path}"
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return "нет onnxruntime"
    return None if load_silero_scorer(model_path) is not None else "контракт модели не подошёл"

def load_silero_scorer(model_path: str | Path, threshold: float = 0.5, source_rate: int = 32000) -> SileroScorer | None:
    """Загружает `silero_vad.onnx` через onnxruntime.

    `None` означает «Silero недоступен»: нет numpy/onnxruntime, нет файла
    модели или контракт не подошёл по probe. Вызывающая сторона в этом случае
    остаётся на `EnergyVad` без изменения остального пайплайна.
    """
    if np is None:
        return None
    path = Path(model_path)
    if not path.is_file():
        return None
    try:
        session = _session_for(path)
        scorer = SileroScorer(session, source_rate=source_rate, threshold=threshold)
    except Exception:
        return None
    return scorer if scorer.probe() else None

def _session_for(path: Path):
    """ONNX-сессия кэшируется: `VadSession` создаётся на каждый listening request,
    а чтение модели с диска не должно попадать в latency первого utterance.
    Состояние Silero живёт в `SileroScorer`, поэтому сессию можно переиспользовать.
    """
    key = str(path.resolve())
    session = _SESSIONS.get(key)
    if session is not None:
        return session
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    _SESSIONS[key] = session
    return session

from __future__ import annotations
import math
from threading import Lock

def percentile(values: list[float], ratio: float) -> float:
    """Nearest-rank перцентиль для ratio в диапазоне 0..1; пустой список даёт 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil(max(0.0, min(1.0, float(ratio))) * len(ordered)) - 1
    return ordered[max(0, min(len(ordered) - 1, index))]

class LatencyLog:
    """Скользящее окно latency по фазам пайплайна с p50/p95.

    Модуль существует ради проверяемых решений об откате рискованных
    оптимизаций (barge-in, preemptive draft, wake word): пока p50/p95 не
    измерены, включать их нельзя. Хранит последние `window` замеров на фазу,
    `regressed()` сравнивает p95 с бюджетом и требует минимум `min_samples`
    замеров, чтобы не откатывать конфигурацию по одному выбросу.
    """
    def __init__(self, window: int = 200, budget_ms: float = 0.0, min_samples: int = 5) -> None:
        self.window = max(1, int(window))
        self.budget_ms = max(0.0, float(budget_ms))
        self.min_samples = max(1, int(min_samples))
        self._samples: dict[str, list[float]] = {}
        self._lock = Lock()
    def record(self, phase: str, ms: float) -> None:
        """Добавляет замер в миллисекундах; отрицательные и NaN/inf игнорируются."""
        try:
            value = float(ms)
        except (TypeError, ValueError):
            return
        if not math.isfinite(value) or value < 0:
            return
        with self._lock:
            samples = self._samples.setdefault(phase, [])
            samples.append(value)
            if len(samples) > self.window:
                del samples[:len(samples) - self.window]
    def samples(self, phase: str) -> list[float]:
        with self._lock:
            return list(self._samples.get(phase, []))
    def p50(self, phase: str) -> float:
        return percentile(self.samples(phase), 0.5)
    def p95(self, phase: str) -> float:
        return percentile(self.samples(phase), 0.95)
    def stats(self) -> dict[str, dict[str, float]]:
        """Снимок окна: фазы без замеров не попадают в результат."""
        with self._lock:
            snapshot = {phase: list(values) for phase, values in self._samples.items() if values}
        return {
            phase: {
                "count": len(values),
                "p50": round(percentile(values, 0.5), 1),
                "p95": round(percentile(values, 0.95), 1),
                "min": round(min(values), 1),
                "max": round(max(values), 1),
            }
            for phase, values in snapshot.items()
        }
    def regressed(self) -> list[str]:
        """Фазы, где p95 выше бюджета: сигнал откатить рискованную оптимизацию.

        Пустой бюджет означает «бюджет не задан» — откат не запрашивается.
        """
        if self.budget_ms <= 0:
            return []
        return sorted(phase for phase, stats in self.stats().items() if stats["count"] >= self.min_samples and stats["p95"] > self.budget_ms)
    def reset(self, phase: str | None = None) -> None:
        with self._lock:
            if phase is None:
                self._samples.clear()
            else:
                self._samples.pop(phase, None)

"""Бэкенды мимики: процедурный риг в UI и опционально NVIDIA Audio2Face-3D.

Разделение ответственности:
* сервер владеет транспортом (gRPC к Audio2Face-3D и его health-эндпоинт) и
  каноническим списком ARKit-шейпов;
* UI владеет маппингом ARKit → морфы конкретной модели (`ui/src/faceMap.ts`),
  потому что возможность управлять выражением определяется файлом аватара.

Audio2Face-3D работает как контейнер NIM (Ubuntu 24.04, RTX-видеокарта, CUDA 12.8+,
образ из NGC) и отдаёт ARKit-подобные 52 веса по стриминговому gRPC. Здесь это не
притворяется работоспособным: если клиентских зависимостей нет или сервис не отвечает,
бэкенд называет причину, а рантайм остаётся на процедурной мимике. См. docs/FACE.md.
"""
from __future__ import annotations

import importlib.util
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

# Значения по умолчанию из документации Audio2Face-3D: gRPC-порт 52000,
# HTTP health — 8000/v1/health/ready (без установки Python-клиента NIM).
A2F_DEFAULT_URL = "127.0.0.1:52000"
A2F_DEFAULT_HEALTH_URL = "http://127.0.0.1:8000/v1/health/ready"

# Канонический список ARKit-шейпов (52), которые приходят в animation header
# Audio2Face-3D. EyeLook* и Head* сервис отдаёт нулями — это его документированное
# поведение, а не ошибка обработки.
ARKIT_BLENDSHAPES: tuple[str, ...] = (
    "BrowDownLeft", "BrowDownRight", "BrowInnerUp", "BrowOuterUpLeft", "BrowOuterUpRight",
    "CheekPuff", "CheekSquintLeft", "CheekSquintRight",
    "EyeBlinkLeft", "EyeBlinkRight", "EyeLookDownLeft", "EyeLookDownRight",
    "EyeLookInLeft", "EyeLookInRight", "EyeLookOutLeft", "EyeLookOutRight",
    "EyeLookUpLeft", "EyeLookUpRight", "EyeSquintLeft", "EyeSquintRight",
    "EyeWideLeft", "EyeWideRight",
    "JawForward", "JawLeft", "JawOpen", "JawRight",
    "MouthClose", "MouthDimpleLeft", "MouthDimpleRight", "MouthFrownLeft",
    "MouthFrownRight", "MouthFunnel", "MouthLeft", "MouthLowerDownLeft",
    "MouthLowerDownRight", "MouthPressLeft", "MouthPressRight", "MouthPucker",
    "MouthRight", "MouthRollLower", "MouthRollUpper", "MouthShrugLower",
    "MouthShrugUpper", "MouthSmileLeft", "MouthSmileRight", "MouthStretchLeft",
    "MouthStretchRight", "MouthUpperUpLeft", "MouthUpperUpRight",
    "NoseSneerLeft", "NoseSneerRight", "TongueOut",
)


def normalize_weights(weights: Mapping[str, Any]) -> dict[str, float]:
    """Приводит веса кадра к диапазону 0..1, отбрасывая нули.

    Неизвестные имена не удаляются: контракт Audio2Face живёт своей жизнью, а решение
    о применимости принимает UI по фактическим морфам модели.
    """
    normalized: dict[str, float] = {}
    for name, raw in weights.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        normalized[str(name)] = value if value < 1 else 1.0
    return normalized


@dataclass(frozen=True)
class FaceFrame:
    """Один кадр мимики: time_code в секундах от начала ответа и веса шейпов."""
    time_code: float
    weights: dict[str, float]

    def as_event(self) -> dict[str, Any]:
        return {
            "type": "face_frame",
            "time_code": round(self.time_code, 4),
            "weights": {name: round(value, 4) for name, value in self.weights.items()},
        }


def frame_from_weights(weights: Mapping[str, Any], time_code: float = 0.0) -> FaceFrame:
    return FaceFrame(time_code=round(float(time_code), 4), weights=normalize_weights(weights))


GRPC_HINT = "нет grpcio/nvidia_ace: стриминговый клиент Audio2Face-3D не установлен"


def grpc_client_available() -> bool:
    """Проверяет клиентские зависимости gRPC без импорта тяжёлых модулей."""
    return all(importlib.util.find_spec(name) is not None for name in ("grpc", "nvidia_ace"))


def http_health_ok(url: str, timeout: float = 1.0) -> bool:
    """GET health-эндпоинта: единственная проверка, не требующая Python-клиента NIM."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", "replace")
            return response.status == 200 and ("ready" in body.lower() or body.strip() in {"", "{}"})
    except (urllib.error.URLError, OSError, ValueError):
        return False


class NullFaceBackend:
    """Мимика без внешнего сервиса: лицом управляет процедурный риг в UI."""

    name = "ui"
    streamed = False

    def available(self) -> bool:
        return False

    def unavailable_reason(self) -> str | None:
        return "внешний бэкенд мимики не выбран: лицо анимирует процедурный риг UI"

    def health(self) -> bool:
        return False

    async def frames(self, audio: bytes, sample_rate: int = 16000) -> list[FaceFrame]:
        """Кадров нет по определению: процедурная мимика считается в браузере."""
        return []


class Audio2FaceBackend:
    """Клиент NVIDIA Audio2Face-3D.

    Реальный стриминг требует grpcio и сгенерированных стабов (`nvidia_ace`), а сам
    сервис — контейнера NIM. Пока зависимостей нет, бэкенд честно объявляет себя
    недоступным и не подменяет мимику выдуманными кадрами.
    """

    name = "audio2face"
    streamed = True

    def __init__(
        self,
        url: str = A2F_DEFAULT_URL,
        health_url: str = A2F_DEFAULT_HEALTH_URL,
        timeout: float = 1.0,
        grpc_available: Callable[[], bool] = grpc_client_available,
        health_probe: Callable[[], bool] | None = None,
    ) -> None:
        self.url = url
        self.health_url = health_url
        self.timeout = timeout
        self._grpc_available = grpc_available
        self._health_probe = health_probe or (lambda: http_health_ok(health_url, timeout))

    def health(self) -> bool:
        return bool(self._health_probe())

    def unavailable_reason(self) -> str | None:
        """Причина, по которой кадры мимики не пойдут. None — бэкенд рабочий."""
        if not self._grpc_available():
            return f"{GRPC_HINT} (gRPC-эндпоинт {self.url})"
        if not self.health():
            return f"Audio2Face-3D не отвечает: {self.health_url}"
        return None

    async def frames(self, audio: bytes, sample_rate: int = 16000) -> list[FaceFrame]:
        """Стартовая точка стриминга ProcessAudioStream; без зависимостей — пустой список."""
        if self.unavailable_reason() is not None:
            return []
        raise NotImplementedError(
            "стриминговый вызов ProcessAudioStream ещё не реализован: нужны grpcio и стабы nvidia_ace"
        )


def a2f_unavailable_reason(
    url: str = A2F_DEFAULT_URL,
    health_url: str = A2F_DEFAULT_HEALTH_URL,
    *,
    grpc_available: Callable[[], bool] = grpc_client_available,
    health_probe: Callable[[], bool] | None = None,
) -> str | None:
    return Audio2FaceBackend(
        url=url, health_url=health_url, grpc_available=grpc_available, health_probe=health_probe
    ).unavailable_reason()


def select_face_backend(settings: Any = None) -> NullFaceBackend | Audio2FaceBackend:
    """Выбор бэкенда мимики по конфигу: неизвестное значение — процедурный риг."""
    name = str(getattr(settings, "face_backend", "ui") or "ui").strip().lower()
    if name in {"audio2face", "a2f", "audio2face3d"}:
        return Audio2FaceBackend(
            url=str(getattr(settings, "a2f_url", A2F_DEFAULT_URL) or A2F_DEFAULT_URL),
            health_url=str(getattr(settings, "a2f_health_url", A2F_DEFAULT_HEALTH_URL) or A2F_DEFAULT_HEALTH_URL),
        )
    return NullFaceBackend()


def describe_face_backend(settings: Any = None) -> str:
    """Строка для `liya doctor`: что управляет мимикой и почему не внешний сервис."""
    backend = select_face_backend(settings)
    reason = backend.unavailable_reason()
    if backend.name == "audio2face":
        state = "доступен" if reason is None else f"недоступен ({reason})"
        return f"Мимика: audio2face, gRPC {backend.url}, health {backend.health_url} — {state}"
    return f"Мимика: процедурный риг UI ({reason})"

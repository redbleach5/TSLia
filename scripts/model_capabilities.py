"""Отчёт о мимике модели: какие morph targets реально есть в файле.

Печатает имена морфов, сгруппированные по префиксам (VRoid Fcl_*, ARKit-подобные),
и сколько из них приходится на лицевые группы. Нужен, чтобы не выдумывать маппинг
ARKit-52: возможность управлять выражением подтверждается наличием морфа в модели.

Запуск:
    python scripts/model_capabilities.py ui/public/models/Lia.gltf
    # Устаревший VRM-файл больше не нужен: текущий runtime использует glTF.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

TARGET_NAMES = re.compile(r'"targetNames"\s*:\s*\[(.*?)\]', re.S)
QUOTED = re.compile(r'"([^"]+)"')
GROUPS = ("Fcl_ALL_", "Fcl_BRW_", "Fcl_EYE_", "Fcl_MTH_", "Fcl_HA_", "Fcl_")


def glb_json(path: Path) -> dict:
    with path.open("rb") as handle:
        magic, _version, _length = struct.unpack("<III", handle.read(12))
        if magic != 0x46546C67:
            raise ValueError("не GLB-контейнер")
        chunk_length, _chunk_type = struct.unpack("<II", handle.read(8))
        return json.loads(handle.read(chunk_length))


def morph_names(path: Path) -> list[str]:
    """Имена морфов: GLB читаем как контейнер, glTF — как JSON (файл может быть большим)."""
    if path.suffix.lower() in {".glb", ".vrm"}:
        document = glb_json(path)
        names: list[str] = []
        for mesh in document.get("meshes", []):
            names.extend((mesh.get("extras") or {}).get("targetNames", []))
        if not names:
            for mesh in document.get("meshes", []):
                for primitive in mesh.get("primitives", []):
                    names.extend((primitive.get("extras") or {}).get("targetNames", []))
        return names
    text = path.read_text(encoding="utf-8", errors="ignore")
    names = []
    for block in TARGET_NAMES.findall(text):
        names.extend(QUOTED.findall(block))
    return names


def report(path: Path) -> int:
    if not path.exists():
        print(f"Модель не найдена: {path}", file=sys.stderr)
        return 1
    names = morph_names(path)
    unique = sorted(set(names))
    print(f"Модель: {path}")
    print(f"Morph targets: {len(unique)} уникальных ({len(names)} записей по мешам)")
    if not unique:
        print("Список пуст: способ управления мимикой в этой модели не подтверждён.")
        return 0
    for prefix in GROUPS:
        group = [name for name in unique if name.startswith(prefix)]
        if group:
            print(f"  {prefix}: {len(group)}")
    unknown = [name for name in unique if not name.startswith("Fcl_")]
    print(f"  без префикса Fcl_: {len(unknown)}" + (f" → {unknown}" if unknown else ""))
    print("Имена:")
    for name in unique:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    targets = sys.argv[1:] or ["ui/public/models/Lia.gltf"]
    raise SystemExit(max(report(Path(target)) for target in targets))

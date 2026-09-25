"""Сверка моста ARKit → морфы (ui/src/faceMap.ts) с каноническим списком и моделью.

Таблица маппинга живёт в UI (там же, где файл аватара), поэтому её согласованность с
серверной стороной и с реальными морфами модели проверяется отдельным тестом. Числа
из этого теста цитируются в docs/FACE.md: 31 из 52 шейпов маппится, 21 — нет.
"""
import importlib.util
import re
from pathlib import Path

import pytest

from liya.face import ARKIT_BLENDSHAPES

ROOT = Path(__file__).resolve().parents[1]
FACE_MAP = ROOT / "ui" / "src" / "faceMap.ts"
MODEL = ROOT / "ui" / "public" / "models" / "Lia.gltf"
TARGET = re.compile(r"\['([A-Za-z]+)','([A-Za-z_0-9]+)',([0-9.]+),")


def source() -> str:
    return FACE_MAP.read_text(encoding="utf-8")


def listed(name: str) -> list[str]:
    match = re.search(rf"export const {name}:ReadonlyArray<string>=\[(.*?)\]", source(), re.S)
    assert match, f"в faceMap.ts нет списка {name}"
    return re.findall(r"'([A-Za-z]+)'", match.group(1))


def table() -> list[tuple[str, str, float]]:
    return [(shape, target, float(gain)) for shape, target, gain in TARGET.findall(source())]


def model_targets() -> list[str]:
    spec = importlib.util.spec_from_file_location("model_capabilities", ROOT / "scripts" / "model_capabilities.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.morph_names(MODEL)


def test_shapes_list_matches_server_side():
    assert listed("ARKIT_SHAPES") == list(ARKIT_BLENDSHAPES)
    assert len(listed("ARKIT_SHAPES")) == 52


def test_table_and_unmapped_cover_every_shape_once():
    mapped = [shape for shape, _, _ in table()]
    unmapped = listed("ARKIT_UNMAPPED")
    assert sorted(mapped + unmapped) == sorted(ARKIT_BLENDSHAPES)
    assert len(set(mapped)) == len(mapped)


def test_documented_coverage_numbers():
    # Эти числа заявлены в docs/FACE.md и STATUS.md — расхождение означает, что
    # документация рассинхронизирована с таблицей.
    assert len(table()) == 31
    assert len(listed("ARKIT_UNMAPPED")) == 21


def test_expected_pairs_and_gains():
    pairs = {shape: (target, gain) for shape, target, gain in table()}
    assert pairs["JawOpen"] == ("Fcl_MTH_A", 1.0)
    assert pairs["EyeBlinkLeft"] == ("Fcl_EYE_Close_L", 1.0)
    assert pairs["EyeBlinkRight"] == ("Fcl_EYE_Close_R", 1.0)
    assert pairs["MouthClose"] == ("Fcl_MTH_Close", 0.8)
    assert pairs["MouthPucker"] == ("Fcl_MTH_U", 0.85)
    assert all(0 < gain <= 1 for _, _, gain in table())
    assert all(target.startswith("Fcl_") for _, target, _ in table())


def test_model_has_every_mapped_target():
    if not MODEL.exists():
        pytest.skip("модель аватара не подключена в ui/public/models")
    available = set(model_targets())
    missing = sorted({target for _, target, _ in table()} - available)
    assert not missing, f"таблица маппинга ссылается на отсутствующие морфы: {missing}"

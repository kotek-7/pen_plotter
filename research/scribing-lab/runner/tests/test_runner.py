from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from scribing_runner.cli import _load_engine, _read_text, _run_engine, build_parser
from scribing_runner.contracts import RunRequest
from scribing_runner.artifacts import default_lab_root, default_run_dir, write_run_artifacts


def test_runner_writes_minimal_artifacts(tmp_path: Path) -> None:
    engine_path = Path(__file__).resolve().parents[2] / "engines" / "basic_stroke_engine"
    engine = _load_engine(engine_path)
    request = RunRequest(text="Hi", seed=1, params={"char_size": "8"})

    result = _run_engine(engine, request)
    artifacts = write_run_artifacts(run_dir=tmp_path / "run", request=request, result=result)

    assert artifacts.trajectory.exists()
    assert artifacts.memo.exists()
    assert artifacts.input_text.exists()
    # runner stays decoupled: preview / gcode / safety are not produced here.
    assert not (artifacts.run_dir / "preview.svg").exists()
    assert not (artifacts.run_dir / "output.gcode").exists()
    assert not (artifacts.run_dir / "safety.json").exists()
    trajectory = json.loads(artifacts.trajectory.read_text(encoding="utf-8"))
    assert trajectory and "pen_state" in trajectory[0]


def test_runner_loads_dictionary_stroke_engine() -> None:
    engine_path = Path(__file__).resolve().parents[2] / "engines" / "dictionary_stroke_engine"
    engine = _load_engine(engine_path)
    request = RunRequest(text="永あいうえおカタカナABC123!?+-=()", seed=1)

    result = _run_engine(engine, request)

    assert result["engine_id"] == "dictionary-stroke-engine"
    assert result["trajectory"]
    sources = result["engine_parameters"]["dictionary"]["sources"]
    kanjivg_source = next(source for source in sources if source["source"] == "kanjivg")
    hershey_source = next(source for source in sources if source["source"] == "hershey")
    assert kanjivg_source["license"] == "CC BY-SA 3.0"
    assert kanjivg_source["release"] == "r20250816"
    assert int(kanjivg_source["character_count"]) >= 6700
    assert hershey_source["license"] == "Hershey Fonts"
    assert "A" in result["engine_parameters"]["dictionary"]["used_chars"]


def test_dictionary_engine_aligns_japanese_to_shared_em_box() -> None:
    engine_path = Path(__file__).resolve().parents[2] / "engines" / "dictionary_stroke_engine"
    engine = _load_engine(engine_path)
    config = engine.EngineConfig()
    y_top = config.paper_height - config.margin_top
    em_top = y_top
    em_bottom = y_top - config.char_size
    em_center = y_top - config.char_size / 2

    def y_extent(text: str) -> tuple[float, float]:
        strokes, _ = engine._layout_text(text, config=config)
        ys = [point[1] for stroke in strokes for point in stroke.points]
        return min(ys), max(ys)

    kanji_lo, kanji_hi = y_extent("永")
    kana_lo, kana_hi = y_extent("あ")

    # Full-width kanji and kana share the same em-box.
    assert em_bottom - 1e-6 <= kanji_lo and kanji_hi <= em_top + 1e-6
    assert em_bottom - 1e-6 <= kana_lo and kana_hi <= em_top + 1e-6
    # Kana is centered on the em-box, not top-anchored as before the fix.
    assert abs((kana_lo + kana_hi) / 2 - em_center) < config.char_size * 0.15
    # The long-vowel mark sits exactly at the em-box center.
    dash_lo, dash_hi = y_extent("ー")
    assert abs((dash_lo + dash_hi) / 2 - em_center) < 1e-6


def test_default_run_dir_uses_datetime_prefix_and_name() -> None:
    run_dir = default_run_dir("basic/stroke engine", run_name="smoke test")

    assert run_dir.parent == default_lab_root() / "runs"
    assert re.fullmatch(r"\d{8}T\d{6}_smoke-test", run_dir.name)


def test_default_run_dir_avoids_existing_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls) -> datetime:
            return cls(2026, 6, 26, 12, 34, 56)

    monkeypatch.setattr("scribing_runner.artifacts.default_lab_root", lambda: tmp_path)
    monkeypatch.setattr("scribing_runner.artifacts.datetime", FixedDateTime)
    first = default_run_dir("engine")
    first.mkdir(parents=True)

    second = default_run_dir("engine")

    assert first.name == "20260626T123456_engine"
    assert second.name == f"{first.name}-02"


def test_cli_accepts_text_as_positional_argument() -> None:
    args = build_parser().parse_args(["Hello", "--seed", "7", "--name", "smoke"])

    assert args.text == "Hello"
    assert args.seed == 7
    assert args.name == "smoke"


def test_read_text_accepts_file(tmp_path: Path) -> None:
    text_file = tmp_path / "input.txt"
    text_file.write_text("From file", encoding="utf-8")

    assert _read_text(None, text_file) == "From file"

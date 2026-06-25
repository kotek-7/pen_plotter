from __future__ import annotations

import json
from pathlib import Path

from scribing_runner.cli import _load_engine, _run_engine
from scribing_runner.contracts import RunRequest
from scribing_runner.artifacts import write_run_artifacts


def test_runner_writes_minimal_artifacts(tmp_path: Path) -> None:
    engine_path = Path(__file__).resolve().parents[2] / "engines" / "basic_stroke_engine"
    engine = _load_engine(engine_path)
    request = RunRequest(text="Hi", seed=1, params={"char_size": "8"})

    result = _run_engine(engine, request)
    artifacts = write_run_artifacts(run_dir=tmp_path / "run", request=request, result=result)

    assert artifacts.preview.exists()
    assert artifacts.gcode.exists()
    assert artifacts.trajectory.exists()
    assert artifacts.memo.exists()
    assert json.loads(artifacts.safety.read_text(encoding="utf-8"))["ok"] is True


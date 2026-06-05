from pathlib import Path

from evaluation_harness.baseline_outline import (
    BaselineOutlineConfig,
    run_baseline_outline,
    run_baseline_outline_batch,
    strokes_to_trajectory,
)
from evaluation_harness.registry import ExperimentRegistry


def test_strokes_to_trajectory_marks_pen_states() -> None:
    import numpy as np

    strokes = [np.array([[1.0, 2.0], [3.0, 2.0]])]

    trajectory = strokes_to_trajectory(
        strokes,
        draw_speed_mm_s=10.0,
        penup_speed_mm_s=100.0,
    )

    assert trajectory[0]["pen_state"] == 0
    assert any(point["pen_state"] == 1 for point in trajectory)
    assert trajectory[-1]["pen_state"] == 0
    assert trajectory[-1]["t"] > trajectory[0]["t"]


def test_run_baseline_outline_registers_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_baseline_outline(
        root=root,
        experiment_id="exp-baseline-test",
        input_text="永",
        seed=1,
        config=BaselineOutlineConfig(jitter=0.0, wobble=0.0, optimize=False, vary_speed=False),
    )

    assert record.generator == "baseline-outline"
    assert record.exporter == "xdraw-gcode"
    assert record.metrics["status"] == "ok"
    assert record.metrics["baseline_stroke_count"] > 0
    for path in record.artifacts.values():
        assert Path(path).exists()

    loaded = ExperimentRegistry(root / "registry.jsonl").get("exp-baseline-test")
    assert loaded.artifacts["gcode"].endswith("output.gcode")
    assert loaded.metrics["baseline_stroke_count"] == record.metrics["baseline_stroke_count"]


def test_run_baseline_outline_batch_writes_summary(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    records = run_baseline_outline_batch(
        root=root,
        input_texts=("永", "あい"),
        seeds=(1, 2),
        config=BaselineOutlineConfig(jitter=0.0, wobble=0.0, optimize=False, vary_speed=False),
    )

    assert len(records) == 4
    assert (root / "summary.json").exists()
    assert (root / "summary.md").exists()
    assert len(ExperimentRegistry(root / "registry.jsonl").load_all()) == 4

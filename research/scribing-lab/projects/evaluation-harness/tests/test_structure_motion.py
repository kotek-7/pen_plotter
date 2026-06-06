from pathlib import Path

from evaluation_harness.compare import compare_against_baseline
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.structure_motion import (
    StructureMotionConfig,
    run_structure_motion,
    run_structure_motion_batch,
)
from evaluation_harness.structure_uniform import run_structure_uniform


def test_run_structure_motion_registers_motion_metrics(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_motion(
        root=root,
        experiment_id="exp-motion-test",
        input_text="永",
        seed=1,
    )

    assert record.generator == "structure-motion"
    assert record.metrics["status"] == "ok"
    assert record.metrics["velocity_peak_count"] > 0
    assert record.metrics["draw_speed_cv"] > 0.0
    assert record.metrics["gcode_safety_ok"] == 1
    assert record.metrics["gcode_safety_violation_count"] == 0
    assert record.metrics["writer_profile_speed_mean_mm_s"] == 40.0
    assert "writer_profile" in record.artifacts
    assert "gcode_safety" in record.artifacts
    assert "too-uniform" not in record.failure_tags
    assert "plotter-unsafe" not in record.failure_tags
    for path in record.artifacts.values():
        assert Path(path).exists()


def test_run_structure_motion_supports_fixed_sentence_inputs(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_motion(
        root=root,
        experiment_id="exp-motion-sentence",
        input_text="今日はよい天気です。",
        seed=1,
    )

    assert record.generator == "structure-motion"
    assert record.metrics["status"] == "ok"
    assert record.metrics["point_count"] > 0
    assert record.metrics["gcode_safety_ok"] == 1


def test_run_structure_motion_fits_long_input_to_page(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_motion(
        root=root,
        experiment_id="exp-motion-long",
        input_text="この文章は、手書きらしさ、速度変動、終筆の違いをまとめて観察するためのものです。",
        seed=1,
        profile_id="fast-casual",
    )

    assert record.metrics["gcode_safety_ok"] == 1
    assert record.metrics["gcode_safety_violation_count"] == 0
    assert "plotter-unsafe" not in record.failure_tags


def test_run_structure_motion_batch_writes_summary(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    records = run_structure_motion_batch(root=root, input_texts=("永",), seeds=(1, 2))

    assert len(records) == 2
    assert (root / "motion_summary.json").exists()
    assert (root / "motion_summary.md").exists()
    assert len(ExperimentRegistry(root / "registry.jsonl").load_all()) == 2
    summary = (root / "motion_summary.md").read_text(encoding="utf-8")
    assert "gcode_safety_ok_count" in summary
    assert "gcode_safety_violation_count" in summary
    assert "layout_variation_mm" in summary


def test_run_structure_motion_records_shape_variation_metrics(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_motion(
        root=root,
        experiment_id="exp-motion-varied",
        input_text="永",
        seed=1,
        config=StructureMotionConfig(shape_variation=0.08),
    )

    assert record.metrics["shape_variation"] == 0.08
    assert record.metrics["shape_variation_mm"] == 0.64
    assert "skeleton-too-rigid" not in record.failure_tags


def test_run_structure_motion_records_layout_variation_metrics(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_motion(
        root=root,
        experiment_id="exp-motion-layout-varied",
        input_text="あいうえお",
        seed=1,
        config=StructureMotionConfig(shape_variation=0.08, layout_variation=0.12),
    )

    assert record.metrics["layout_variation"] == 0.12
    assert record.metrics["layout_variation_mm"] == 0.96
    assert "line-too-mechanical" not in record.failure_tags


def test_structure_motion_resolves_too_uniform_against_structure_uniform(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    baseline = run_structure_uniform(
        root=root,
        experiment_id="exp-structure",
        input_text="永",
        seed=1,
    )
    candidate = run_structure_motion(
        root=root,
        experiment_id="exp-motion",
        input_text="永",
        seed=1,
    )

    comparison = compare_against_baseline(
        [baseline, candidate],
        baseline_generator="structure-uniform",
    )

    assert comparison["comparison_count"] == 1
    assert "too-uniform" in comparison["comparisons"][0]["resolved_failure_tags"]


def test_structure_motion_profile_changes_timing_and_pressure(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    baseline = run_structure_motion(
        root=root,
        experiment_id="exp-motion-baseline",
        input_text="永",
        seed=1,
        profile_id="baseline-neat",
    )
    fast = run_structure_motion(
        root=root,
        experiment_id="exp-motion-fast",
        input_text="永",
        seed=1,
        profile_id="fast-casual",
    )

    assert fast.metrics["writer_profile_speed_mean_mm_s"] == 54.0
    assert fast.metrics["writer_profile_timing_jitter_cv"] == 0.14
    assert fast.metrics["duration_ms"] != baseline.metrics["duration_ms"]

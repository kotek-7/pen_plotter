from pathlib import Path

from evaluation_harness.baseline_outline import BaselineOutlineConfig, run_baseline_outline
from evaluation_harness.compare import compare_against_baseline
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.structure_uniform import run_structure_uniform, run_structure_uniform_batch


def test_run_structure_uniform_registers_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    record = run_structure_uniform(
        root=root,
        experiment_id="exp-structure-test",
        input_text="永",
        seed=1,
    )

    assert record.generator == "structure-uniform"
    assert record.metrics["status"] == "ok"
    assert record.metrics["structure_stroke_count"] == 5
    assert "skeleton-too-rigid" in record.failure_tags
    for path in record.artifacts.values():
        assert Path(path).exists()

    loaded = ExperimentRegistry(root / "registry.jsonl").get("exp-structure-test")
    assert loaded.artifacts["stroke_templates"].endswith("stroke_templates.json")


def test_run_structure_uniform_batch_writes_summary(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    records = run_structure_uniform_batch(root=root, input_texts=("永",), seeds=(1, 2))

    assert len(records) == 2
    assert (root / "structure_summary.json").exists()
    assert (root / "structure_summary.md").exists()


def test_structure_uniform_can_be_compared_with_baseline(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    baseline = run_baseline_outline(
        root=root,
        experiment_id="exp-baseline",
        input_text="永",
        seed=1,
        config=BaselineOutlineConfig(jitter=0.0, wobble=0.0, optimize=False, vary_speed=False),
    )
    candidate = run_structure_uniform(
        root=root,
        experiment_id="exp-structure",
        input_text="永",
        seed=1,
    )

    comparison = compare_against_baseline([baseline, candidate])

    assert comparison["comparison_count"] == 1
    assert comparison["comparisons"][0]["candidate_generator"] == "structure-uniform"

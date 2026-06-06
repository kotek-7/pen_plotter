from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.compare import (
    compare_against_baseline,
    compare_fixed_input_set,
    render_comparison_markdown,
    render_fixed_input_comparison_markdown,
)
from evaluation_harness.models import ExperimentRecord


def test_compare_against_baseline_reports_metric_deltas() -> None:
    baseline = ExperimentRecord(
        experiment_id="exp-baseline",
        hypothesis="baseline",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="baseline-outline",
        exporter="xdraw-gcode",
        metrics={"duration_ms": 1000, "draw_speed_cv": 0.0},
        failure_tags=["too-font-like", "terminal-too-uniform"],
    )
    candidate = ExperimentRecord(
        experiment_id="exp-candidate",
        hypothesis="candidate",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="structure-uniform",
        exporter="xdraw-gcode",
        metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
        failure_tags=["terminal-too-uniform"],
    )

    comparison = compare_against_baseline([baseline, candidate])

    assert comparison["comparison_count"] == 1
    item = comparison["comparisons"][0]
    assert item["metric_deltas"]["duration_ms"] == -100.0
    assert item["metric_deltas"]["draw_speed_cv"] == 0.2
    assert item["resolved_failure_tags"] == ["too-font-like"]


def test_render_comparison_markdown_handles_no_candidates() -> None:
    baseline = ExperimentRecord(
        experiment_id="exp-baseline",
        hypothesis="baseline",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="baseline-outline",
        exporter="xdraw-gcode",
    )

    report = render_comparison_markdown(compare_against_baseline([baseline]))

    assert "# Baseline Comparison Report" in report
    assert "- none" in report


def test_compare_fixed_input_set_reports_complete_coverage() -> None:
    records = [
        _record(
            experiment_id=f"exp-baseline-{index}-{seed}",
            input_text=input_text,
            seed=seed,
            generator="baseline-outline",
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS[:2], start=1)
        for seed in (1, 2)
    ]
    records.extend(
        _record(
            experiment_id=f"exp-candidate-{index}-{seed}",
            input_text=input_text,
            seed=seed,
            generator="structure-uniform",
            metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
            failure_tags=["terminal-too-uniform"],
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS[:2], start=1)
        for seed in (1, 2)
    )

    comparison = compare_fixed_input_set(
        records,
        expected_input_texts=DEFAULT_EVALUATION_INPUTS[:2],
        expected_seeds=(1, 2),
    )

    assert comparison["expected_group_count"] == 4
    assert comparison["complete_group_count"] == 4
    assert comparison["coverage_ratio"] == 1.0
    assert all(item["status"] == "complete" for item in comparison["group_summaries"])
    report = render_fixed_input_comparison_markdown(comparison)
    assert "# Fixed Input Comparison Report" in report
    assert "coverage_ratio" in report


def test_compare_fixed_input_set_reports_missing_baselines() -> None:
    comparison = compare_fixed_input_set(
        [
            _record(
                experiment_id="exp-candidate",
                input_text="永",
                seed=1,
                generator="structure-uniform",
                metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
            )
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert comparison["complete_group_count"] == 0
    assert comparison["coverage_ratio"] == 0.0
    assert comparison["group_summaries"][0]["status"] == "missing-baseline"


def _record(
    *,
    experiment_id: str,
    input_text: str,
    seed: int,
    generator: str,
    metrics: dict[str, float | int | str] | None = None,
    failure_tags: list[str] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        metrics=metrics or {},
        failure_tags=failure_tags or [],
    )

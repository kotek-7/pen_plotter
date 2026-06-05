from evaluation_harness.compare import compare_against_baseline, render_comparison_markdown
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

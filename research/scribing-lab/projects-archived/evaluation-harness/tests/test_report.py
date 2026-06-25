from evaluation_harness.models import ExperimentRecord
from evaluation_harness.report import render_markdown_report


def test_render_markdown_report_includes_review_fields() -> None:
    record = ExperimentRecord(
        experiment_id="exp-000001",
        hypothesis="test hypothesis",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="test-generator",
        exporter="test-exporter",
        artifacts={"trajectory": "artifacts/exp-000001/trajectory.json"},
        metrics={"stroke_count": 1},
        failure_tags=["too-uniform"],
        next_action="increase timing variation",
    )

    report = render_markdown_report(record)

    assert "# Experiment exp-000001" in report
    assert "test hypothesis" in report
    assert "`too-uniform`" in report
    assert "increase timing variation" in report

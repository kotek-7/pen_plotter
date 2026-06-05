from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import (
    build_offline_review,
    infer_offline_failure_tags,
    render_offline_review_markdown,
    review_record,
)


def test_infer_offline_failure_tags_detects_uniform_motion() -> None:
    record = _record(
        metrics={
            "point_count": 12,
            "velocity_peak_count": 0,
            "draw_speed_cv": 0.02,
        }
    )

    assert "too-uniform" in infer_offline_failure_tags(record)


def test_infer_offline_failure_tags_detects_plotter_unsafe() -> None:
    record = _record(
        generator="structure-motion",
        metrics={
            "point_count": 12,
            "velocity_peak_count": 3,
            "draw_speed_cv": 0.3,
            "gcode_safety_ok": 0,
            "gcode_safety_violation_count": 2,
        },
    )

    tags = infer_offline_failure_tags(record)

    assert "plotter-unsafe" in tags
    assert "skeleton-too-rigid" in tags


def test_infer_offline_failure_tags_detects_mechanical_line() -> None:
    record = _record(
        input_text="あいうえお",
        metrics={
            "point_count": 20,
            "velocity_peak_count": 4,
            "draw_speed_cv": 0.2,
            "visible_char_count": 5,
            "stroke_start_spacing_cv": 0.01,
            "baseline_drift_mm": 0.2,
        },
    )

    assert "line-too-mechanical" in infer_offline_failure_tags(record)


def test_infer_offline_failure_tags_detects_over_jittered() -> None:
    record = _record(
        metrics={
            "point_count": 12,
            "velocity_peak_count": 8,
            "draw_speed_cv": 1.4,
            "mean_abs_jerk_mm_s3": 1000.0,
        }
    )

    assert "over-jittered" in infer_offline_failure_tags(record)


def test_review_record_suggests_next_actions() -> None:
    item = review_record(
        _record(
            metrics={
                "point_count": 12,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.02,
            }
        )
    )

    assert "too-uniform" in item.inferred_failure_tags
    assert item.suggested_next_actions


def test_build_and_render_offline_review() -> None:
    review = build_offline_review(
        [
            _record(
                experiment_id="exp-a",
                metrics={
                    "point_count": 12,
                    "velocity_peak_count": 0,
                    "draw_speed_cv": 0.02,
                },
            )
        ]
    )

    report = render_offline_review_markdown(review)

    assert review["record_count"] == 1
    assert review["failure_tag_counts"]["too-uniform"] == 1
    assert "# Offline Review" in report
    assert "suggested_next_actions" in report


def _record(
    *,
    experiment_id: str = "exp-001",
    input_text: str = "永",
    generator: str = "structure-uniform",
    metrics: dict[str, float | int | str] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=1,
        generator=generator,
        exporter="xdraw-gcode",
        metrics=metrics or {},
    )

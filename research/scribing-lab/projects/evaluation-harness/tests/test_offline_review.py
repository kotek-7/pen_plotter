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


def test_infer_offline_failure_tags_resolves_skeleton_rigidity_with_shape_variation() -> None:
    record = _record(
        generator="structure-motion",
        metrics={
            "point_count": 12,
            "velocity_peak_count": 3,
            "draw_speed_cv": 0.3,
            "shape_variation": 0.08,
            "shape_variation_mm": 0.64,
        },
        failure_tags=["skeleton-too-rigid"],
    )

    assert "skeleton-too-rigid" not in infer_offline_failure_tags(record)


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


def test_infer_offline_failure_tags_resolves_mechanical_line_with_layout_variation() -> None:
    record = _record(
        input_text="あいうえお",
        generator="structure-motion",
        metrics={
            "point_count": 20,
            "velocity_peak_count": 4,
            "draw_speed_cv": 0.2,
            "visible_char_count": 5,
            "stroke_start_spacing_cv": 0.01,
            "baseline_drift_mm": 0.2,
            "layout_variation": 0.12,
            "layout_variation_mm": 0.96,
        },
        failure_tags=["line-too-mechanical"],
    )

    assert "line-too-mechanical" not in infer_offline_failure_tags(record)


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


def test_infer_offline_failure_tags_detects_small_layout() -> None:
    record = _record(
        metrics={
            "point_count": 12,
            "velocity_peak_count": 2,
            "draw_speed_cv": 0.2,
            "visible_char_count": 5,
            "line_count": 1,
            "ink_bbox_width_mm": 18.0,
            "ink_bbox_height_mm": 6.0,
        }
    )

    assert "too-small" in infer_offline_failure_tags(record)


def test_infer_offline_failure_tags_detects_wide_spacing() -> None:
    record = _record(
        metrics={
            "point_count": 12,
            "velocity_peak_count": 2,
            "draw_speed_cv": 0.2,
            "visible_char_count": 5,
            "line_count": 1,
            "ink_bbox_width_mm": 75.0,
            "ink_bbox_height_mm": 10.0,
            "mean_stroke_start_gap_mm": 18.0,
        }
    )

    assert "spacing-too-wide" in infer_offline_failure_tags(record)


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
    assert item.tag_groups["motion"] == ["too-uniform"]
    assert item.rule_hits
    assert item.confidence > 0.0


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
    assert review["failure_tag_group_counts"]["motion"] == 1
    assert review["mean_confidence"] > 0.0
    assert "# Offline Review" in report
    assert "suggested_next_actions" in report
    assert "robustness" in report


def test_build_offline_review_reports_robustness_ok() -> None:
    records = [
        _record(
            experiment_id=f"exp-{seed}",
            seed=seed,
            input_text="あいうえお",
            generator="structure-motion",
            metrics={
                "point_count": 20,
                "velocity_peak_count": 4,
                "draw_speed_cv": 0.2,
                "mean_abs_jerk_mm_s3": 10000.0 + seed,
                "visible_char_count": 5,
                "layout_variation_mm": 0.96,
                "shape_variation_mm": 0.64,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        )
        for seed in (1, 2, 3)
    ]

    review = build_offline_review(records)

    assert review["robustness"]["status"] == "ok"
    assert review["robustness"]["failing_record_count"] == 0
    assert review["robustness"]["unsafe_record_count"] == 0
    assert review["robustness"]["uncertain_record_ids"]


def test_build_offline_review_reports_unstable_metric_groups() -> None:
    records = [
        _record(
            experiment_id=f"exp-{seed}",
            seed=seed,
            input_text="永",
            generator="structure-motion",
            metrics={
                "point_count": 20,
                "velocity_peak_count": 4,
                "draw_speed_cv": draw_speed_cv,
                "shape_variation_mm": 0.64,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        )
        for seed, draw_speed_cv in ((1, 0.2), (2, 0.25), (3, 0.7))
    ]

    review = build_offline_review(records)

    assert review["robustness"]["unstable_metric_groups"] == [
        {
            "generator": "structure-motion",
            "input_text": "永",
            "metric": "draw_speed_cv",
            "range": 0.5,
        }
    ]


def _record(
    *,
    experiment_id: str = "exp-001",
    input_text: str = "永",
    seed: int = 1,
    generator: str = "structure-uniform",
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

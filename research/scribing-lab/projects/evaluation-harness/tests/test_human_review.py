from evaluation_harness.human_review import (
    build_human_review_packet,
    render_human_review_packet_markdown,
)
from evaluation_harness.models import ExperimentRecord


def test_build_human_review_packet_selects_representatives() -> None:
    records = [
        _record(
            "exp-repeat",
            input_text="あああ",
            seed=1,
            metrics={
                "draw_speed_cv": 0.2,
                "mean_abs_jerk_mm_s3": 1000.0,
                "stroke_start_spacing_cv": 1.0,
                "baseline_drift_mm": 3.0,
                "repeated_char_ratio": 0.6667,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-newline",
            input_text="あい\nうえ",
            seed=2,
            metrics={
                "draw_speed_cv": 0.3,
                "mean_abs_jerk_mm_s3": 1200.0,
                "baseline_drift_mm": 4.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-jerk",
            input_text="永",
            seed=3,
            metrics={
                "draw_speed_cv": 0.5,
                "mean_abs_jerk_mm_s3": 5000.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
    ]

    packet = build_human_review_packet(records)

    ids = [item["experiment_id"] for item in packet["representatives"]]
    assert "exp-repeat" in ids
    assert "exp-newline" in ids
    assert "exp-jerk" in ids
    assert packet["robustness"]["status"] == "ok"


def test_render_human_review_packet_markdown_includes_preview_paths() -> None:
    packet = build_human_review_packet(
        [
            _record(
                "exp-a",
                input_text="永",
                seed=1,
                metrics={
                    "draw_speed_cv": 0.2,
                    "mean_abs_jerk_mm_s3": 1000.0,
                    "shape_variation_mm": 0.64,
                    "layout_variation_mm": 0.96,
                    "gcode_safety_ok": 1,
                    "gcode_safety_violation_count": 0,
                },
            )
        ]
    )

    report = render_human_review_packet_markdown(packet)

    assert "# Human Review Packet" in report
    assert "preview.png" in report
    assert "Records By Input" in report


def _record(
    experiment_id: str,
    *,
    input_text: str,
    seed: int,
    metrics: dict[str, float | int | str],
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=seed,
        generator="structure-motion",
        exporter="xdraw-gcode",
        artifacts={"preview": f"artifacts/{experiment_id}/preview.png"},
        metrics=metrics,
    )

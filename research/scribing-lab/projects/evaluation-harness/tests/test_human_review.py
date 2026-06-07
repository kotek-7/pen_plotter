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
    assert packet["robustness"]["uncertain_record_ids"]


def test_build_human_review_packet_scales_with_larger_record_sets() -> None:
    records = [
        _record(
            f"exp-{index:02d}",
            input_text="永",
            seed=index,
            metrics={
                "draw_speed_cv": 0.2 + index * 0.01,
                "mean_abs_jerk_mm_s3": 1000.0 + index * 10.0,
                "stroke_start_spacing_cv": 0.1,
                "baseline_drift_mm": 0.2,
                "repeated_char_ratio": 0.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        )
        for index in range(40)
    ]

    packet = build_human_review_packet(records)

    assert packet["representative_count"] == 20
    assert len(packet["representatives"]) == 20
    assert packet["representatives"][0]["experiment_id"].startswith("exp-")


def test_build_human_review_packet_reflects_script_groups() -> None:
    records = [
        _record(
            "exp-kana",
            input_text="あいう",
            seed=1,
            metrics={
                "draw_speed_cv": 0.2,
                "mean_abs_jerk_mm_s3": 1000.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-kanji",
            input_text="永日本",
            seed=2,
            metrics={
                "draw_speed_cv": 0.3,
                "mean_abs_jerk_mm_s3": 1200.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-latin",
            input_text="ABC",
            seed=3,
            metrics={
                "draw_speed_cv": 0.4,
                "mean_abs_jerk_mm_s3": 1300.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-digit",
            input_text="012",
            seed=4,
            metrics={
                "draw_speed_cv": 0.5,
                "mean_abs_jerk_mm_s3": 1400.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
        _record(
            "exp-punct",
            input_text="、。",
            seed=5,
            metrics={
                "draw_speed_cv": 0.6,
                "mean_abs_jerk_mm_s3": 1500.0,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        ),
    ]

    packet = build_human_review_packet(records)
    groups = {
        group
        for item in packet["representatives"]
        for group in item.get("input_script_groups", [])
    }

    assert {"kana", "kanji", "latin", "digit", "punctuation"} <= groups
    assert packet["script_group_counts"]["kana"] == 1
    assert packet["script_group_counts"]["kanji"] == 1
    assert packet["script_group_counts"]["latin"] == 1


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

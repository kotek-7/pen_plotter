from evaluation_harness.human_feedback_loop import (
    build_human_feedback_loop,
    build_human_review_response_template,
    render_human_feedback_loop_markdown,
    render_human_review_response_template_markdown,
    summarize_human_review_draft_rows,
)
from evaluation_harness.models import ExperimentRecord


def test_build_human_feedback_loop_without_responses_returns_template() -> None:
    record = _record("exp-a", generator="baseline-outline")

    loop = build_human_feedback_loop([record], reviewer_id="reviewer-1")

    assert loop["loop_status"] == "awaiting_response"
    assert loop["response_summary"] is None
    assert loop["response_template"]["reviewer_id"] == "reviewer-1"
    assert loop["response_template"]["responses"][0]["experiment_id"] == "exp-a"
    assert loop["response_template"]["responses"][0]["input_script_groups"] == ["kanji"]
    assert "response_template を埋めて" in loop["next_actions"][0]


def test_build_human_feedback_loop_with_responses_summarizes_next_actions() -> None:
    record = _record("exp-a", generator="structure-motion")

    loop = build_human_feedback_loop(
        [record],
        responses_data={
            "responses": [
                {
                    "experiment_id": "exp-a",
                    "decision": "needs-tuning",
                    "reason_tags": ["spacing-too-wide"],
                    "notes": "字間が広い",
                    "reviewer_id": "reviewer-1",
                }
            ]
        },
        reviewer_id="reviewer-1",
    )

    assert loop["loop_status"] == "needs_tuning"
    assert loop["response_summary"]["can_proceed_to_plot"] is False
    assert loop["response_summary"]["decision_counts"] == {"needs-tuning": 1}
    assert any("line spacing" in action for action in loop["next_actions"])
    assert loop["calibration_summary"] is not None
    assert loop["calibration_summary"]["reviewed_response_count"] == 1
    assert loop["agreement_summary"] is not None
    assert "Calibration Summary" in render_human_feedback_loop_markdown(loop)


def test_build_human_feedback_loop_reports_agreement_for_multiple_reviewers() -> None:
    record = _record("exp-a", generator="structure-motion")

    loop = build_human_feedback_loop(
        [record],
        responses_data={
            "responses": [
                {
                    "experiment_id": "exp-a",
                    "decision": "accept",
                    "reviewer_id": "r1",
                },
                {
                    "experiment_id": "exp-a",
                    "decision": "accept",
                    "reviewer_id": "r2",
                },
            ]
        },
        reviewer_id="r1",
    )

    assert loop["agreement_summary"]["reviewer_count"] == 2
    assert loop["agreement_summary"]["mean_cohen_kappa"] == 1.0
    assert "Agreement Summary" in render_human_feedback_loop_markdown(loop)


def test_render_human_feedback_loop_markdown_includes_sections() -> None:
    record = _record("exp-a", generator="baseline-outline")
    loop = build_human_feedback_loop([record])

    report = render_human_feedback_loop_markdown(loop)

    assert "# Human Feedback Loop" in report
    assert "Response Template" in report
    assert "Next Actions" in report


def test_render_human_review_response_template_markdown_includes_axes() -> None:
    record = _record("exp-a", generator="baseline-outline")
    packet = build_human_feedback_loop([record])["packet"]
    template = build_human_review_response_template(packet, reviewer_id="reviewer-1")

    report = render_human_review_response_template_markdown(template)

    assert "# Human Review Response Template" in report
    assert "Review Axes" in report
    assert "reviewer-1" in report


def test_summarize_human_review_draft_rows_handles_partial_input() -> None:
    packet = build_human_feedback_loop([_record("exp-a", generator="baseline-outline")])["packet"]

    summary = summarize_human_review_draft_rows(
        packet,
        [
            {
                "experiment_id": "exp-a",
                "decision": "",
                "reason_tags": [],
                "notes": "",
                "reviewer_id": "reviewer-1",
            }
        ],
    )

    assert summary["can_proceed_to_plot"] is False
    assert summary["missing_response_ids"] == ["exp-a"]
    assert "missing decision: exp-a" in summary["validation_errors"]


def test_summarize_human_review_draft_rows_allows_negative_decision_with_reason_tags() -> None:
    packet = build_human_feedback_loop([_record("exp-a", generator="baseline-outline")])["packet"]

    summary = summarize_human_review_draft_rows(
        packet,
        [
            {
                "experiment_id": "exp-a",
                "decision": "reject",
                "reason_tags": ["spacing-too-wide"],
                "notes": "字間が広い",
                "reviewer_id": "reviewer-1",
            }
        ],
    )

    assert summary["validation_errors"] == []
    assert summary["decision_counts"] == {"reject": 1}
    assert summary["can_proceed_to_plot"] is False


def _record(experiment_id: str, *, generator: str) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts={"preview": f"artifacts/{experiment_id}/preview.png"},
        metrics={
            "draw_speed_cv": 0.01,
            "mean_abs_jerk_mm_s3": 50.0,
            "stroke_start_spacing_cv": 0.02,
            "baseline_drift_mm": 0.2,
            "repeated_char_ratio": 0.0,
            "shape_variation_mm": 0.1,
            "layout_variation_mm": 0.1,
            "gcode_safety_ok": 1,
            "gcode_safety_violation_count": 0,
            "visible_char_count": 1,
            "ink_bbox_width_mm": 8.0,
            "ink_bbox_height_mm": 10.0,
            "mean_stroke_start_gap_mm": 1.0,
        },
    )

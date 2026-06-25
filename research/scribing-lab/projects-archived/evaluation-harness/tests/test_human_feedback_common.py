from pathlib import Path

from evaluation_harness.human_feedback_common import (
    HumanFeedbackDraft,
    build_common_failure_examples,
    build_decision_help,
    build_review_instructions,
    choose_font_family,
    load_feedback_packet,
    load_response_drafts,
    serialize_response_drafts,
    validate_response_drafts,
)
from evaluation_harness.human_review_response import HumanReviewResponse


def test_choose_font_family_prefers_first_available_candidate() -> None:
    family = choose_font_family(
        {"Meiryo", "DejaVu Sans"},
        ("Yu Gothic", "Meiryo", "DejaVu Sans"),
        fallback="Default",
    )

    assert family == "Meiryo"


def test_choose_font_family_is_case_insensitive() -> None:
    family = choose_font_family(
        {"nimbus sans l", "nimbus mono l"},
        ("Nimbus Sans L", "Nimbus Mono L"),
        fallback="Default",
    )

    assert family == "nimbus sans l"


def test_choose_font_family_falls_back_to_default() -> None:
    family = choose_font_family({"Unrelated Font"}, ("Yu Gothic", "Meiryo"), fallback="Default")

    assert family == "Default"


def test_build_review_instructions_are_stepwise() -> None:
    instructions = build_review_instructions()

    assert instructions[0].startswith("1.")
    assert len(instructions) == 4
    assert "Export Responses" in instructions[-1]


def test_build_decision_help_mentions_all_decisions() -> None:
    help_lines = build_decision_help()

    assert any(line.startswith("accept:") for line in help_lines)
    assert any(line.startswith("needs-tuning:") for line in help_lines)
    assert any(line.startswith("reject:") for line in help_lines)


def test_build_common_failure_examples_cover_known_problems() -> None:
    examples = build_common_failure_examples()

    assert any("文字が小さすぎる" in line for line in examples)
    assert any("字間" in line for line in examples)
    assert any("ひっくり返る" in line for line in examples)


def test_load_response_drafts_round_trip(tmp_path: Path) -> None:
    packet = {
        "representatives": [
            {"experiment_id": "exp-a"},
            {"experiment_id": "exp-b"},
        ]
    }
    responses_json = tmp_path / "responses.json"
    responses_json.write_text(
        """
        {
          "responses": [
            {
              "experiment_id": "exp-a",
              "decision": "accept",
              "reason_tags": [],
              "notes": "ok",
              "reviewer_id": "rev-1"
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    drafts = load_response_drafts(packet=packet, responses_json=responses_json, reviewer_id="rev-0")

    assert drafts["exp-a"].decision == "accept"
    assert drafts["exp-a"].reviewer_id == "rev-1"
    assert drafts["exp-b"].reviewer_id == "rev-0"

    payload = serialize_response_drafts(drafts)
    assert payload["responses"][0]["experiment_id"] == "exp-a"


def test_load_feedback_packet_supports_longform_sort_order(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    registry_path = root / "registry.jsonl"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        "\n".join(
            [
                """
                {"experiment_id":"exp-short","hypothesis":"test","input_text":"永","profile_id":"baseline-neat","seed":1,"generator":"baseline-outline","exporter":"preview","artifacts":{"preview":"artifacts/exp-short/preview.png"},"metrics":{"draw_speed_cv":0.01,"mean_abs_jerk_mm_s3":50.0,"stroke_start_spacing_cv":0.02,"baseline_drift_mm":0.2,"repeated_char_ratio":0.0,"shape_variation_mm":0.1,"layout_variation_mm":0.1,"gcode_safety_ok":1,"gcode_safety_violation_count":0,"visible_char_count":1,"ink_bbox_width_mm":8.0,"ink_bbox_height_mm":10.0,"mean_stroke_start_gap_mm":1.0},"failure_tags":[],"next_action":"keep baseline comparison","notes":""}
                """.strip(),
                """
                {"experiment_id":"exp-long","hypothesis":"test","input_text":"ASCII ABCDEFGH と abcdefgh も評価する。","profile_id":"baseline-neat","seed":1,"generator":"baseline-outline","exporter":"preview","artifacts":{"preview":"artifacts/exp-long/preview.png"},"metrics":{"draw_speed_cv":0.01,"mean_abs_jerk_mm_s3":50.0,"stroke_start_spacing_cv":0.02,"baseline_drift_mm":0.2,"repeated_char_ratio":0.0,"shape_variation_mm":0.1,"layout_variation_mm":0.1,"gcode_safety_ok":1,"gcode_safety_violation_count":0,"visible_char_count":1,"ink_bbox_width_mm":8.0,"ink_bbox_height_mm":10.0,"mean_stroke_start_gap_mm":1.0},"failure_tags":[],"next_action":"keep baseline comparison","notes":""}
                """.strip(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    packet = load_feedback_packet(root=root, sort_order="longform-first")

    assert packet["sort_order"] == "longform-first"
    assert packet["representatives"][0]["experiment_id"] == "exp-long"


def test_validate_response_drafts_reports_missing_entries() -> None:
    packet = {"representatives": [{"experiment_id": "exp-a"}, {"experiment_id": "exp-b"}]}
    drafts = {
        "exp-a": HumanFeedbackDraft(
            experiment_id="exp-a",
            decision="accept",
        ),
        "exp-b": HumanFeedbackDraft(
            experiment_id="exp-b",
        ),
    }

    summary = validate_response_drafts(packet, drafts)

    assert summary["missing_response_ids"] == ["exp-b"]
    assert summary["can_proceed_to_plot"] is False


def test_validate_response_drafts_accepts_response_objects() -> None:
    packet = {"representatives": [{"experiment_id": "exp-a"}]}
    response = HumanReviewResponse(
        experiment_id="exp-a",
        decision="accept",
    )
    drafts = {"exp-a": HumanFeedbackDraft.from_response(response)}

    summary = validate_response_drafts(packet, drafts)

    assert summary["can_proceed_to_plot"] is True

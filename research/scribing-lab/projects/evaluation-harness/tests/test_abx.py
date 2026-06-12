import pytest

from evaluation_harness.abx import (
    AbxItem,
    AbxResponse,
    build_abx_revision_plan,
    build_abx_response_template,
    build_human_abx_feedback_loop,
    load_abx_responses,
    render_abx_summary_markdown,
    render_abx_revision_plan_markdown,
    render_abx_feedback_loop_markdown,
    render_abx_response_template_markdown,
    summarize_abx_responses,
    validate_abx_response,
)


def test_summarize_abx_responses_counts_choices() -> None:
    summary = summarize_abx_responses(
        [
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="A", confidence=4),
            AbxResponse(item_id="item-1", evaluator_id="eval-2", choice="B", confidence=2),
            AbxResponse(item_id="item-2", evaluator_id="eval-1", choice="tie", confidence=3),
        ]
    )

    assert summary["response_count"] == 3
    assert summary["choice_counts"] == {"A": 1, "B": 1, "tie": 1}
    assert summary["mean_confidence"] == 3.0
    assert summary["by_item"]["item-1"] == {"A": 1, "B": 1, "tie": 0}
    assert summary["tie_rate"] == pytest.approx(1 / 3)
    assert summary["duplicate_pairs"] == []
    assert summary["evaluator_counts"] == {"eval-1": 2, "eval-2": 1}
    assert summary["uncertain_items"] == ["item-2"]


def test_summarize_abx_responses_reports_expected_preference_accuracy() -> None:
    summary = summarize_abx_responses(
        [
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="A", confidence=4),
            AbxResponse(item_id="item-1", evaluator_id="eval-2", choice="A", confidence=3),
            AbxResponse(item_id="item-2", evaluator_id="eval-1", choice="tie", confidence=2),
        ],
        items=[
            AbxItem(
                item_id="item-1",
                prompt="p",
                option_a_artifact="a",
                option_b_artifact="b",
                question="q",
                expected_preference="A",
            ),
            AbxItem(
                item_id="item-2",
                prompt="p",
                option_a_artifact="a",
                option_b_artifact="b",
                question="q",
                expected_preference="tie",
            ),
        ],
    )

    assert summary["expected_preference_count"] == 2
    assert summary["expected_preference_accuracy"] == 1.0
    assert summary["preference_margin_by_item"]["item-1"] == 1.0
    assert summary["confidence_by_choice"]["A"]["mean"] == 3.5
    assert summary["bradley_terry_strengths"]["a"] > summary["bradley_terry_strengths"]["b"]
    assert summary["bradley_terry_ranking"][0] == "a"
    report = render_abx_summary_markdown(summary)
    assert "# ABX Summary" in report
    assert "Bradley-Terry" in report


def test_validate_abx_response_rejects_invalid_choice() -> None:
    with pytest.raises(ValueError, match="choice"):
        validate_abx_response(
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="C", confidence=4)
        )


def test_validate_abx_response_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        validate_abx_response(
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="A", confidence=0)
        )


def test_summarize_abx_responses_rejects_duplicate_pairs() -> None:
    summary = summarize_abx_responses(
        [
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="A", confidence=4),
            AbxResponse(item_id="item-1", evaluator_id="eval-1", choice="B", confidence=3),
        ]
    )

    assert summary["duplicate_pairs"] == ["item-1:eval-1"]


def test_build_abx_response_template_and_feedback_loop() -> None:
    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "永",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "kanji-tight",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-candidate",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": [],
                "selected_next_actions": [],
            }
        ]
    }

    template = build_abx_response_template(packet, evaluator_id="eval-1")
    assert template["item_count"] == 1
    assert template["allowed_choices"] == ["A", "B", "tie"]
    assert template["responses"][0]["evaluator_id"] == "eval-1"
    assert "Response Template" in render_abx_response_template_markdown(template)

    loop = build_human_abx_feedback_loop(packet)
    assert loop["loop_status"] == "pending"
    assert loop["next_actions"] == ["ABX responses を収集する"]
    assert "ABX Feedback Loop" in render_abx_feedback_loop_markdown(loop)


def test_load_abx_responses_supports_response_dict() -> None:
    responses = load_abx_responses(
        {
            "responses": [
                {
                    "item_id": "item-1",
                    "evaluator_id": "eval-1",
                    "choice": "A",
                    "confidence": 4,
                    "note": "good",
                }
            ]
        }
    )

    assert len(responses) == 1
    assert responses[0].choice == "A"
    assert responses[0].note == "good"


def test_build_human_abx_feedback_loop_limits_items_by_profile() -> None:
    packet = {
        "abx_items": [
            {
                "item_id": f"item-{index}",
                "prompt": "永",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": profile_id,
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": f"exp-{profile_id}-{index}",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": [],
                "selected_next_actions": [],
            }
            for index, profile_id in enumerate(
                ["a", "a", "b", "b", "c", "c", "d", "d"],
                start=1,
            )
        ]
    }

    loop = build_human_abx_feedback_loop(packet, max_items=3)

    assert len(loop["packet"]["abx_items"]) == 3
    assert {item["candidate_profile_id"] for item in loop["packet"]["abx_items"]} == {"a", "b", "c"}


def test_build_human_abx_feedback_loop_summarizes_responses() -> None:
    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "永",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "kanji-tight",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-candidate",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": [],
                "selected_next_actions": [],
            },
            {
                "item_id": "item-2",
                "prompt": "？",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-candidate-2",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": [],
                "selected_next_actions": [],
            },
        ]
    }
    responses = {
        "responses": [
            {
                "item_id": "item-2",
                "evaluator_id": "eval-1",
                "choice": "B",
                "confidence": 4,
            }
        ]
    }

    loop = build_human_abx_feedback_loop(packet, responses_data=responses)

    assert loop["loop_status"] == "ready"
    assert loop["response_summary"]["response_count"] == 1
    assert loop["response_summary"]["choice_counts"] == {"A": 0, "B": 1, "tie": 0}
    assert loop["response_summary"]["bradley_terry_ranking"]


def test_build_abx_revision_plan_uses_response_summary() -> None:
    loop = {
        "loop_status": "ready",
        "packet": {
            "abx_items": [
                {
                    "item_id": "item-1",
                    "prompt": "永",
                    "candidate_profile_id": "kanji-tight",
                    "selected_failure_tags": ["over-jittered"],
                    "selected_next_actions": ["motion-synthesis の tremor / timing jitter を下げる"],
                },
                {
                    "item_id": "item-2",
                    "prompt": "？",
                    "candidate_profile_id": "symbol-neat",
                    "selected_failure_tags": ["spacing-too-wide"],
                    "selected_next_actions": ["character advance と line spacing を詰める"],
                },
            ]
        },
        "response_summary": {
            "response_count": 1,
            "by_item": {"item-2": {"A": 0, "B": 1, "tie": 0}},
        },
    }

    plan = build_abx_revision_plan(loop)

    assert plan["response_count"] == 1
    assert plan["selected_item_count"] == 1
    assert plan["items"][0]["item_id"] == "item-2"
    assert plan["items"][0]["focus_area"] == "layout"
    assert "ABX Revision Plan" in render_abx_revision_plan_markdown(plan)

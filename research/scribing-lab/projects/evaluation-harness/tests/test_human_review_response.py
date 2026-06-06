import pytest

from evaluation_harness.human_review_response import (
    HumanReviewResponse,
    cohen_kappa,
    load_human_review_responses,
    summarize_human_review_calibration,
    summarize_human_review_agreement,
    render_human_review_response_markdown,
    summarize_human_review_responses,
)


def test_human_review_response_accepts_known_decision() -> None:
    response = HumanReviewResponse(
        experiment_id="exp-a",
        decision="accept",
        reviewer_id="reviewer-1",
    )

    assert response.to_dict()["decision"] == "accept"


def test_human_review_response_requires_reason_for_reject() -> None:
    with pytest.raises(ValueError, match="reason_tags"):
        HumanReviewResponse(experiment_id="exp-a", decision="reject")


def test_summarize_human_review_responses_allows_plot_when_all_representatives_accept() -> None:
    packet = _packet(["exp-a", "exp-b"])
    responses = [
        HumanReviewResponse(experiment_id="exp-a", decision="accept"),
        HumanReviewResponse(experiment_id="exp-b", decision="accept"),
    ]

    summary = summarize_human_review_responses(packet, responses)

    assert summary["can_proceed_to_plot"] is True
    assert summary["validation_errors"] == []
    assert summary["decision_counts"] == {"accept": 2}


def test_summarize_human_review_responses_reports_missing_and_unknown_ids() -> None:
    packet = _packet(["exp-a", "exp-b"])
    responses = [
        HumanReviewResponse(experiment_id="exp-a", decision="accept"),
        HumanReviewResponse(
            experiment_id="exp-x",
            decision="needs-tuning",
            reason_tags=["preview-shape-odd"],
        ),
    ]

    summary = summarize_human_review_responses(packet, responses)

    assert summary["can_proceed_to_plot"] is False
    assert summary["missing_response_ids"] == ["exp-b"]
    assert summary["unknown_response_ids"] == ["exp-x"]
    assert summary["decision_counts"] == {"accept": 1, "needs-tuning": 1}


def test_load_human_review_responses_accepts_wrapped_object() -> None:
    responses = load_human_review_responses(
        {
            "responses": [
                {"experiment_id": "exp-a", "decision": "accept"},
            ]
        }
    )

    assert responses == [HumanReviewResponse(experiment_id="exp-a", decision="accept")]


def test_render_human_review_response_markdown() -> None:
    summary = summarize_human_review_responses(
        _packet(["exp-a"]),
        [HumanReviewResponse(experiment_id="exp-a", decision="accept")],
    )

    report = render_human_review_response_markdown(summary)

    assert "# Human Review Response Summary" in report
    assert "can_proceed_to_plot" in report
    assert "exp-a" in report


def test_summarize_human_review_calibration_reports_adjustments() -> None:
    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "failure_tags": ["too-uniform", "terminal-too-uniform"],
            },
            {
                "experiment_id": "exp-b",
                "failure_tags": ["too-uniform"],
            },
            {
                "experiment_id": "exp-c",
                "failure_tags": ["too-font-like"],
            },
        ]
    }
    responses = [
        HumanReviewResponse(experiment_id="exp-a", decision="accept"),
        HumanReviewResponse(
            experiment_id="exp-b",
            decision="reject",
            reason_tags=["too-uniform"],
        ),
        HumanReviewResponse(
            experiment_id="exp-c",
            decision="needs-tuning",
            reason_tags=["too-font-like"],
        ),
    ]

    calibration = summarize_human_review_calibration(packet, responses)

    assert calibration["tag_decision_counts"]["too-uniform"]["accept"] == 1
    assert calibration["tag_decision_counts"]["too-uniform"]["reject"] == 1
    assert calibration["reason_tag_alignment"] > 0.0
    assert calibration["recommended_adjustments"]


def test_summarize_human_review_agreement_reports_kappa() -> None:
    responses = [
        HumanReviewResponse(experiment_id="exp-a", decision="accept", reviewer_id="r1"),
        HumanReviewResponse(experiment_id="exp-b", decision="reject", reviewer_id="r1", reason_tags=["spacing-too-wide"]),
        HumanReviewResponse(experiment_id="exp-a", decision="accept", reviewer_id="r2"),
        HumanReviewResponse(experiment_id="exp-b", decision="reject", reviewer_id="r2", reason_tags=["spacing-too-wide"]),
    ]

    agreement = summarize_human_review_agreement(responses)

    assert agreement["reviewer_count"] == 2
    assert agreement["mean_cohen_kappa"] == 1.0
    assert agreement["mean_reason_tag_jaccard"] == 1.0


def test_cohen_kappa_handles_perfect_and_partial_agreement() -> None:
    assert cohen_kappa(["accept", "reject"], ["accept", "reject"]) == 1.0
    assert cohen_kappa(["accept", "reject"], ["accept", "accept"]) < 1.0


def _packet(experiment_ids: list[str]) -> dict[str, object]:
    return {
        "representatives": [
            {"experiment_id": experiment_id}
            for experiment_id in experiment_ids
        ]
    }

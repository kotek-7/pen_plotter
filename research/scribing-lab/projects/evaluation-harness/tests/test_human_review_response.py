import pytest

from evaluation_harness.human_review_response import (
    HumanReviewResponse,
    load_human_review_responses,
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


def _packet(experiment_ids: list[str]) -> dict[str, object]:
    return {
        "representatives": [
            {"experiment_id": experiment_id}
            for experiment_id in experiment_ids
        ]
    }

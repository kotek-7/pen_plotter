import pytest

from evaluation_harness.abx import (
    AbxItem,
    AbxResponse,
    render_abx_summary_markdown,
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

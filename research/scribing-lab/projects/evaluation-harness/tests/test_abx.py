import pytest

from evaluation_harness.abx import AbxResponse, summarize_abx_responses, validate_abx_response


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

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AbxItem:
    item_id: str
    prompt: str
    option_a_artifact: str
    option_b_artifact: str
    question: str
    expected_preference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AbxResponse:
    item_id: str
    evaluator_id: str
    choice: str
    confidence: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_abx_response(response: AbxResponse) -> None:
    if response.choice not in {"A", "B", "tie"}:
        raise ValueError("choice must be A, B, or tie")
    if not 1 <= response.confidence <= 5:
        raise ValueError("confidence must be between 1 and 5")
    if not response.item_id.strip() or not response.evaluator_id.strip():
        raise ValueError("item_id and evaluator_id are required")


def summarize_abx_responses(responses: list[AbxResponse]) -> dict[str, Any]:
    for response in responses:
        validate_abx_response(response)

    choice_counts = {"A": 0, "B": 0, "tie": 0}
    confidence_sum = 0
    by_item: dict[str, dict[str, int]] = {}
    for response in responses:
        choice_counts[response.choice] += 1
        confidence_sum += response.confidence
        item_counts = by_item.setdefault(response.item_id, {"A": 0, "B": 0, "tie": 0})
        item_counts[response.choice] += 1

    return {
        "response_count": len(responses),
        "choice_counts": choice_counts,
        "mean_confidence": round(confidence_sum / len(responses), 4) if responses else 0.0,
        "by_item": by_item,
    }

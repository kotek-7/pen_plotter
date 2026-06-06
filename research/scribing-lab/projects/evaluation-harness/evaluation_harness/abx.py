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


def validate_abx_responses(responses: list[AbxResponse]) -> dict[str, list[str]]:
    for response in responses:
        validate_abx_response(response)

    duplicate_pairs: dict[tuple[str, str], int] = {}
    for response in responses:
        pair = (response.item_id, response.evaluator_id)
        duplicate_pairs[pair] = duplicate_pairs.get(pair, 0) + 1
    duplicates = sorted(f"{item_id}:{evaluator_id}" for (item_id, evaluator_id), count in duplicate_pairs.items() if count > 1)
    return {"duplicate_pairs": duplicates}


def summarize_abx_responses(
    responses: list[AbxResponse],
    *,
    items: list[AbxItem] | None = None,
) -> dict[str, Any]:
    validation = validate_abx_responses(responses)

    choice_counts = {"A": 0, "B": 0, "tie": 0}
    confidence_sum = 0
    by_item: dict[str, dict[str, int]] = {}
    evaluator_counts: dict[str, int] = {}
    confidence_by_choice: dict[str, list[int]] = {"A": [], "B": [], "tie": []}
    bt_strengths = _fit_bradley_terry_strengths(items or [], responses) if items else {}
    for response in responses:
        choice_counts[response.choice] += 1
        confidence_sum += response.confidence
        item_counts = by_item.setdefault(response.item_id, {"A": 0, "B": 0, "tie": 0})
        item_counts[response.choice] += 1
        evaluator_counts[response.evaluator_id] = evaluator_counts.get(response.evaluator_id, 0) + 1
        confidence_by_choice[response.choice].append(response.confidence)

    expected_by_item = {item.item_id: item.expected_preference for item in items or [] if item.expected_preference}
    correctness = 0
    comparable = 0
    preference_margin_by_item: dict[str, float] = {}
    uncertain_items: list[str] = []
    for item_id, counts in by_item.items():
        total = sum(counts.values())
        if total > 0:
            preference_margin_by_item[item_id] = round(abs(counts["A"] - counts["B"]) / total, 4)
        if counts["tie"] >= max(counts["A"], counts["B"]):
            uncertain_items.append(item_id)
        expected = expected_by_item.get(item_id)
        if expected in {"A", "B", "tie"}:
            comparable += 1
            predicted = max(counts.items(), key=lambda kv: (kv[1], {"A": 2, "B": 1, "tie": 0}[kv[0]]))[0]
            if predicted == expected:
                correctness += 1

    return {
        "response_count": len(responses),
        "choice_counts": choice_counts,
        "mean_confidence": round(confidence_sum / len(responses), 4) if responses else 0.0,
        "by_item": by_item,
        "evaluator_counts": dict(sorted(evaluator_counts.items())),
        "tie_rate": choice_counts["tie"] / len(responses) if responses else 0.0,
        "duplicate_pairs": validation["duplicate_pairs"],
        "confidence_by_choice": {
            choice: {
                "count": len(values),
                "mean": round(sum(values) / len(values), 4) if values else 0.0,
            }
            for choice, values in confidence_by_choice.items()
        },
        "preference_margin_by_item": dict(sorted(preference_margin_by_item.items())),
        "uncertain_items": sorted(uncertain_items),
        "expected_preference_count": comparable,
        "expected_preference_accuracy": round(correctness / comparable, 4) if comparable else 0.0,
        "bradley_terry_strengths": bt_strengths,
        "bradley_terry_ranking": sorted(
            bt_strengths,
            key=lambda item_id: bt_strengths[item_id],
            reverse=True,
        ),
    }


def render_abx_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# ABX Summary",
        "",
        f"- response_count: `{summary['response_count']}`",
        f"- choice_counts: `{summary['choice_counts']}`",
        f"- mean_confidence: `{summary['mean_confidence']}`",
        f"- tie_rate: `{summary['tie_rate']}`",
        f"- expected_preference_count: `{summary['expected_preference_count']}`",
        f"- expected_preference_accuracy: `{summary['expected_preference_accuracy']}`",
        f"- evaluator_counts: `{summary['evaluator_counts']}`",
        f"- duplicate_pairs: `{summary['duplicate_pairs']}`",
        f"- uncertain_items: `{summary['uncertain_items']}`",
        "",
        "## Bradley-Terry",
        "",
    ]
    if summary["bradley_terry_ranking"]:
        for item_id in summary["bradley_terry_ranking"]:
            lines.append(
                f"- {item_id}: `{summary['bradley_terry_strengths'].get(item_id, 0.0)}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## By Item", ""])
    for item_id, counts in sorted(summary["by_item"].items()):
        lines.append(f"- {item_id}: `{counts}`")
    return "\n".join(lines) + "\n"


def _fit_bradley_terry_strengths(
    items: list[AbxItem],
    responses: list[AbxResponse],
    *,
    max_iter: int = 500,
    tol: float = 1e-8,
    ridge: float = 1e-6,
) -> dict[str, float]:
    if not items or not responses:
        return {}

    wins: dict[tuple[str, str], float] = {}
    comparisons: dict[tuple[str, str], float] = {}
    strengths: dict[str, float] = {}

    for item in items:
        strengths.setdefault(item.option_a_artifact, 1.0)
        strengths.setdefault(item.option_b_artifact, 1.0)

    for response in responses:
        item = next((item for item in items if item.item_id == response.item_id), None)
        if item is None:
            continue
        a = item.option_a_artifact
        b = item.option_b_artifact
        _add_compare(comparisons, a, b, 1.0)
        _add_compare(comparisons, b, a, 1.0)
        if response.choice == "A":
            _add_win(wins, a, b, 1.0)
        elif response.choice == "B":
            _add_win(wins, b, a, 1.0)
        else:
            _add_win(wins, a, b, 0.5)
            _add_win(wins, b, a, 0.5)

    if len(strengths) < 2:
        return {key: 0.0 for key in strengths}

    for _ in range(max_iter):
        max_delta = 0.0
        new_strengths: dict[str, float] = {}
        for item_i, current_strength in strengths.items():
            numerator = sum(wins.get((item_i, item_j), 0.0) for item_j in strengths if item_j != item_i)
            denominator = 0.0
            for item_j, other_strength in strengths.items():
                if item_j == item_i:
                    continue
                total_compares = comparisons.get((item_i, item_j), 0.0)
                if total_compares == 0.0:
                    continue
                denominator += total_compares / max(current_strength + other_strength, ridge)
            if denominator <= 0.0:
                new_strength = current_strength
            else:
                new_strength = max(numerator, ridge) / max(denominator, ridge)
            new_strengths[item_i] = new_strength
            max_delta = max(max_delta, abs(new_strength - current_strength))
        strengths = new_strengths
        if max_delta < tol:
            break

    min_strength = min(strengths.values())
    normalized = {item_id: max(strength - min_strength + 1.0, ridge) for item_id, strength in strengths.items()}
    return {item_id: round(score, 6) for item_id, score in sorted(normalized.items())}


def _add_win(wins: dict[tuple[str, str], float], winner: str, loser: str, amount: float) -> None:
    wins[(winner, loser)] = wins.get((winner, loser), 0.0) + amount


def _add_compare(
    comparisons: dict[tuple[str, str], float],
    left: str,
    right: str,
    amount: float,
) -> None:
    comparisons[(left, right)] = comparisons.get((left, right), 0.0) + amount

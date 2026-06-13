from __future__ import annotations

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass, field
import itertools
from typing import Any


DECISIONS: frozenset[str] = frozenset({"accept", "reject", "needs-tuning"})


@dataclass(frozen=True)
class HumanReviewResponse:
    experiment_id: str
    decision: str
    reason_tags: list[str] = field(default_factory=list)
    notes: str = ""
    reviewer_id: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if self.decision not in DECISIONS:
            raise ValueError(f"unknown decision: {self.decision}")
        if self.decision in {"reject", "needs-tuning"} and not self.reason_tags:
            raise ValueError("reason_tags are required for reject or needs-tuning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "decision": self.decision,
            "reason_tags": list(self.reason_tags),
            "notes": self.notes,
            "reviewer_id": self.reviewer_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HumanReviewResponse:
        return cls(
            experiment_id=str(data["experiment_id"]),
            decision=str(data["decision"]),
            reason_tags=[str(tag) for tag in data.get("reason_tags", [])],
            notes=str(data.get("notes", "")),
            reviewer_id=str(data.get("reviewer_id", "")),
        )


def load_human_review_responses(data: Any) -> list[HumanReviewResponse]:
    raw_responses = data.get("responses", data) if isinstance(data, dict) else data
    if not isinstance(raw_responses, list):
        raise ValueError("human review responses must be a list or an object with responses")
    return [HumanReviewResponse.from_dict(item) for item in raw_responses]


def summarize_human_review_responses(
    packet: dict[str, Any],
    responses: list[HumanReviewResponse],
) -> dict[str, Any]:
    representative_ids = {
        str(item["experiment_id"])
        for item in packet.get("representatives", [])
    }
    response_ids = [response.experiment_id for response in responses]
    duplicate_ids = sorted(
        experiment_id
        for experiment_id, count in Counter(response_ids).items()
        if count > 1
    )
    unknown_ids = sorted(set(response_ids) - representative_ids)
    missing_ids = sorted(representative_ids - set(response_ids))
    decision_counts = dict(sorted(Counter(response.decision for response in responses).items()))
    reason_tag_counts = dict(
        sorted(Counter(tag for response in responses for tag in response.reason_tags).items())
    )
    note_examples = [
        {
            "experiment_id": response.experiment_id,
            "decision": response.decision,
            "reason_tags": list(response.reason_tags),
            "notes": response.notes.strip(),
            "reviewer_id": response.reviewer_id,
        }
        for response in responses
        if response.notes.strip()
    ]
    note_count = len(note_examples)
    note_char_count = sum(len(item["notes"]) for item in note_examples)
    validation_errors = []
    validation_errors.extend(f"unknown experiment_id: {experiment_id}" for experiment_id in unknown_ids)
    validation_errors.extend(f"missing response: {experiment_id}" for experiment_id in missing_ids)
    validation_errors.extend(f"duplicate response: {experiment_id}" for experiment_id in duplicate_ids)
    can_proceed_to_plot = (
        not validation_errors
        and decision_counts.get("reject", 0) == 0
        and decision_counts.get("needs-tuning", 0) == 0
        and decision_counts.get("accept", 0) == len(representative_ids)
    )
    return {
        "representative_count": len(representative_ids),
        "response_count": len(responses),
        "decision_counts": decision_counts,
        "reason_tag_counts": reason_tag_counts,
        "note_count": note_count,
        "note_char_count": note_char_count,
        "note_examples": note_examples,
        "missing_response_ids": missing_ids,
        "unknown_response_ids": unknown_ids,
        "duplicate_response_ids": duplicate_ids,
        "validation_errors": validation_errors,
        "can_proceed_to_plot": can_proceed_to_plot,
        "responses": [response.to_dict() for response in responses],
    }


def summarize_human_review_calibration(
    packet: dict[str, Any],
    responses: list[HumanReviewResponse],
) -> dict[str, Any]:
    representative_by_id = {
        str(item["experiment_id"]): item
        for item in packet.get("representatives", [])
    }
    tag_decision_counts: dict[str, Counter[str]] = defaultdict(Counter)
    tag_response_counts: Counter[str] = Counter()
    aligned_reason_tags = 0
    reason_tag_total = 0

    for response in responses:
        item = representative_by_id.get(response.experiment_id)
        if item is None:
            continue
        item_tags = [str(tag) for tag in item.get("failure_tags", [])]
        if response.decision != "accept":
            reason_tag_total += len(response.reason_tags)
            if set(response.reason_tags) & set(item_tags):
                aligned_reason_tags += 1
        for tag in item_tags:
            tag_decision_counts[tag][response.decision] += 1
            tag_response_counts[tag] += 1

    tag_profiles: list[dict[str, Any]] = []
    recommended_adjustments: list[str] = []
    for tag, counts in sorted(tag_decision_counts.items()):
        total = sum(counts.values())
        accept_rate = round(counts.get("accept", 0) / total, 4) if total else 0.0
        negative_rate = round(
            (counts.get("reject", 0) + counts.get("needs-tuning", 0)) / total,
            4,
        ) if total else 0.0
        if accept_rate >= 0.6:
            adjustment = f"{tag}: 阈値を厳しくして false positive を減らす"
        elif negative_rate >= 0.6:
            adjustment = f"{tag}: 現状の判定は妥当なので維持または強化する"
        else:
            adjustment = f"{tag}: 判定が揺れているため追加レビューを集める"
        tag_profiles.append(
            {
                "tag": tag,
                "decision_counts": dict(sorted(counts.items())),
                "sample_count": total,
                "accept_rate": accept_rate,
                "negative_rate": negative_rate,
                "adjustment": adjustment,
            }
        )
        if adjustment not in recommended_adjustments:
            recommended_adjustments.append(adjustment)

    uncertain_tags = [
        item["tag"]
        for item in tag_profiles
        if 0.4 <= item["accept_rate"] <= 0.6 and item["sample_count"] > 0
    ]
    overtriggered_tags = [
        item["tag"]
        for item in tag_profiles
        if item["accept_rate"] >= 0.6 and item["sample_count"] > 0
    ]
    supported_tags = [
        item["tag"]
        for item in tag_profiles
        if item["negative_rate"] >= 0.6 and item["sample_count"] > 0
    ]
    reason_tag_alignment = round(aligned_reason_tags / reason_tag_total, 4) if reason_tag_total else 0.0

    return {
        "tag_profiles": tag_profiles,
        "tag_decision_counts": {
            tag: dict(sorted(counts.items()))
            for tag, counts in sorted(tag_decision_counts.items())
        },
        "tag_response_counts": dict(sorted(tag_response_counts.items())),
        "overtriggered_tags": overtriggered_tags,
        "supported_tags": supported_tags,
        "uncertain_tags": uncertain_tags,
        "reason_tag_alignment": reason_tag_alignment,
        "recommended_adjustments": recommended_adjustments,
        "reviewed_response_count": len(responses),
    }


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a and labels_b must have the same length")
    if not labels_a:
        return 0.0

    categories = sorted(set(labels_a) | set(labels_b))
    if len(categories) <= 1:
        return 1.0

    observed = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / len(labels_a)
    a_counts = Counter(labels_a)
    b_counts = Counter(labels_b)
    expected = sum(
        (a_counts[category] / len(labels_a)) * (b_counts[category] / len(labels_b))
        for category in categories
    )
    if expected == 1.0:
        return 1.0
    return round((observed - expected) / (1.0 - expected), 4)


def summarize_human_review_agreement(responses: list[HumanReviewResponse]) -> dict[str, Any]:
    by_item: dict[str, list[HumanReviewResponse]] = defaultdict(list)
    for response in responses:
        by_item[response.experiment_id].append(response)

    pairwise_kappas: list[dict[str, Any]] = []
    pairwise_jaccard: list[dict[str, Any]] = []
    overlapping_items = 0
    for (reviewer_a, responses_a), (reviewer_b, responses_b) in itertools.combinations(
        _group_responses_by_reviewer(responses).items(),
        2,
    ):
        items_a = {response.experiment_id: response for response in responses_a}
        items_b = {response.experiment_id: response for response in responses_b}
        common_ids = sorted(set(items_a) & set(items_b))
        if not common_ids:
            continue
        overlapping_items += len(common_ids)
        labels_a = [items_a[item_id].decision for item_id in common_ids]
        labels_b = [items_b[item_id].decision for item_id in common_ids]
        pairwise_kappas.append(
            {
                "reviewer_a": reviewer_a,
                "reviewer_b": reviewer_b,
                "item_count": len(common_ids),
                "cohen_kappa": cohen_kappa(labels_a, labels_b),
                "agreement_rate": round(
                    sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / len(common_ids),
                    4,
                ),
            }
        )
        pairwise_jaccard.append(
            {
                "reviewer_a": reviewer_a,
                "reviewer_b": reviewer_b,
                "item_count": len(common_ids),
                "mean_reason_tag_jaccard": _mean_reason_tag_jaccard(
                    [items_a[item_id].reason_tags for item_id in common_ids],
                    [items_b[item_id].reason_tags for item_id in common_ids],
                ),
            }
        )

    mean_kappa = (
        round(sum(item["cohen_kappa"] for item in pairwise_kappas) / len(pairwise_kappas), 4)
        if pairwise_kappas
        else 0.0
    )
    mean_reason_jaccard = (
        round(
            sum(item["mean_reason_tag_jaccard"] for item in pairwise_jaccard) / len(pairwise_jaccard),
            4,
        )
        if pairwise_jaccard
        else 0.0
    )
    return {
        "reviewer_count": len(_group_responses_by_reviewer(responses)),
        "overlapping_item_count": overlapping_items,
        "pairwise_kappas": pairwise_kappas,
        "pairwise_reason_tag_jaccard": pairwise_jaccard,
        "mean_cohen_kappa": mean_kappa,
        "mean_reason_tag_jaccard": mean_reason_jaccard,
    }


def _group_responses_by_reviewer(
    responses: list[HumanReviewResponse],
) -> dict[str, list[HumanReviewResponse]]:
    grouped: dict[str, list[HumanReviewResponse]] = defaultdict(list)
    for response in responses:
        grouped[response.reviewer_id or "anonymous"].append(response)
    return grouped


def _mean_reason_tag_jaccard(
    tags_a: list[list[str]],
    tags_b: list[list[str]],
) -> float:
    if not tags_a:
        return 0.0
    scores: list[float] = []
    for left, right in zip(tags_a, tags_b, strict=True):
        left_set = set(left)
        right_set = set(right)
        union = left_set | right_set
        if not union:
            scores.append(1.0)
        else:
            scores.append(len(left_set & right_set) / len(union))
    return round(sum(scores) / len(scores), 4)


def render_human_review_response_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Human Review Response Summary",
        "",
        f"- representative_count: `{summary['representative_count']}`",
        f"- response_count: `{summary['response_count']}`",
        f"- decision_counts: `{summary['decision_counts']}`",
        f"- reason_tag_counts: `{summary['reason_tag_counts']}`",
        f"- note_count: `{summary.get('note_count', 0)}`",
        f"- note_char_count: `{summary.get('note_char_count', 0)}`",
        f"- can_proceed_to_plot: `{summary['can_proceed_to_plot']}`",
        "",
        "## Validation",
        "",
    ]
    if summary["validation_errors"]:
        lines.extend(f"- {error}" for error in summary["validation_errors"])
    else:
        lines.append("- ok")

    lines.extend(["", "## Responses", ""])
    if not summary["responses"]:
        lines.append("- none")
    for response in summary["responses"]:
        lines.append(
            "- "
            f"{response['experiment_id']}: "
            f"decision=`{response['decision']}`, "
            f"reason_tags=`{response['reason_tags']}`, "
            f"reviewer_id=`{response['reviewer_id']}`"
        )
        if response["notes"]:
            lines.append(f"  - notes: {response['notes']}")
    lines.extend(["", "## Notes", ""])
    note_examples = summary.get("note_examples", [])
    if not note_examples:
        lines.append("- none")
    else:
        for note in note_examples:
            lines.append(
                "- "
                f"{note['experiment_id']}: "
                f"decision=`{note['decision']}`, "
                f"reason_tags=`{note['reason_tags']}`, "
                f"reviewer_id=`{note['reviewer_id']}`"
            )
            lines.append(f"  - notes: {note['notes']}")
    return "\n".join(lines) + "\n"

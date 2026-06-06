from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
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
        "missing_response_ids": missing_ids,
        "unknown_response_ids": unknown_ids,
        "duplicate_response_ids": duplicate_ids,
        "validation_errors": validation_errors,
        "can_proceed_to_plot": can_proceed_to_plot,
        "responses": [response.to_dict() for response in responses],
    }


def render_human_review_response_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Human Review Response Summary",
        "",
        f"- representative_count: `{summary['representative_count']}`",
        f"- response_count: `{summary['response_count']}`",
        f"- decision_counts: `{summary['decision_counts']}`",
        f"- reason_tag_counts: `{summary['reason_tag_counts']}`",
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
    return "\n".join(lines) + "\n"

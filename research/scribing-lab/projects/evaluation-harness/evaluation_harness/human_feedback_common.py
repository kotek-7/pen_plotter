from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from evaluation_harness.human_feedback_loop import build_human_feedback_loop, summarize_human_review_draft_rows
from evaluation_harness.human_review_response import HumanReviewResponse
from evaluation_harness.registry import ExperimentRegistry


@dataclass
class HumanFeedbackDraft:
    experiment_id: str
    decision: str = ""
    reason_tags: list[str] = field(default_factory=list)
    notes: str = ""
    reviewer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "decision": self.decision,
            "reason_tags": list(self.reason_tags),
            "notes": self.notes,
            "reviewer_id": self.reviewer_id,
        }

    @classmethod
    def from_response(cls, response: HumanReviewResponse) -> HumanFeedbackDraft:
        return cls(
            experiment_id=response.experiment_id,
            decision=response.decision,
            reason_tags=list(response.reason_tags),
            notes=response.notes,
            reviewer_id=response.reviewer_id,
        )


def load_feedback_packet(
    *,
    root: Path | None = None,
    packet_json: Path | None = None,
    target_count: int | None = None,
    sort_order: str = "default",
) -> dict[str, Any]:
    if packet_json is not None:
        packet_data = json.loads(packet_json.read_text(encoding="utf-8"))
        return packet_data["packet"] if "packet" in packet_data else packet_data
    if root is None:
        raise ValueError("root or packet_json is required")
    registry = ExperimentRegistry(root / "registry.jsonl")
    return build_human_feedback_loop(
        registry.load_all(),
        target_count=target_count,
        sort_order=sort_order,
    )["packet"]


def load_response_drafts(
    *,
    packet: dict[str, Any],
    responses_json: Path | None = None,
    reviewer_id: str = "",
) -> dict[str, HumanFeedbackDraft]:
    drafts = {
        str(item["experiment_id"]): HumanFeedbackDraft(
            experiment_id=str(item["experiment_id"]),
            reviewer_id=reviewer_id,
        )
        for item in packet.get("representatives", [])
    }
    if responses_json is None or not responses_json.exists():
        return drafts

    data = json.loads(responses_json.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "responses" in data:
            raw_responses = data["responses"]
        elif isinstance(data.get("response_summary"), dict) and "responses" in data["response_summary"]:
            raw_responses = data["response_summary"]["responses"]
        else:
            raw_responses = data
    else:
        raw_responses = data
    if not isinstance(raw_responses, list):
        raise ValueError("responses_json must contain a list or an object with responses")

    for raw in raw_responses:
        response = HumanReviewResponse.from_dict(raw)
        if response.experiment_id in drafts:
            drafts[response.experiment_id] = HumanFeedbackDraft.from_response(response)
    return drafts


def serialize_response_drafts(drafts: dict[str, HumanFeedbackDraft]) -> dict[str, Any]:
    return {
        "responses": [
            drafts[experiment_id].to_dict()
            for experiment_id in sorted(drafts)
            if drafts[experiment_id].decision
        ]
    }


def validate_response_drafts(
    packet: dict[str, Any],
    drafts: dict[str, HumanFeedbackDraft],
) -> dict[str, Any]:
    rows = [draft.to_dict() for draft in drafts.values()]
    return summarize_human_review_draft_rows(packet, rows)


def choose_font_family(
    available_families: Iterable[str],
    candidates: Sequence[str],
    *,
    fallback: str,
) -> str:
    available_set = set(available_families)
    available_by_lower = {family.lower(): family for family in available_families}
    for family in candidates:
        if family in available_set:
            return family
        resolved = available_by_lower.get(family.lower())
        if resolved is not None:
            return resolved
    return fallback


def build_review_instructions() -> list[str]:
    return [
        "1. 左の一覧から対象を選ぶ。",
        "2. preview を見て、文字の大きさ・字間・形の破綻を確認する。",
        "3. accept / reject / needs-tuning を選び、理由タグを付ける。",
        "4. Validate で確認し、Export Responses で保存する。",
    ]


def build_decision_help() -> list[str]:
    return [
        "accept: このまま次へ進めてよい。",
        "needs-tuning: 方向は合っているが、見た目の調整が必要。",
        "reject: 文字が崩れている、または別方向に直すべき。",
    ]


def build_common_failure_examples() -> list[str]:
    return [
        "よく見る欠陥: 文字が小さすぎる。",
        "よく見る欠陥: 字間が空きすぎている。",
        "よく見る欠陥: 文字がひっくり返る、または向きが不自然。",
        "よく見る欠陥: 「い」の形が崩れる。",
        "よく見る欠陥: 全体が機械的で均一すぎる。",
    ]


def build_review_guide_lines() -> list[str]:
    return [
        "Review steps",
        *build_review_instructions(),
        "",
        "Decision hints",
        *build_decision_help(),
        "",
        *build_common_failure_examples(),
    ]


def render_review_guide_markdown() -> str:
    return "\n".join(build_review_guide_lines()) + "\n"

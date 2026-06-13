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


def build_human_review_start_card(
    packet: dict[str, Any],
    summary: dict[str, Any],
    *,
    sort_order: str = "default",
) -> dict[str, Any]:
    representatives = list(packet.get("representatives", []))
    note_count = int(summary.get("note_count", 0))
    response_count = int(sum(summary.get("decision_counts", {}).values()))

    if summary.get("can_proceed_to_plot"):
        loop_status = "ready"
    elif response_count == 0:
        loop_status = "awaiting_response"
    elif summary.get("validation_errors"):
        loop_status = "needs_fix"
    else:
        loop_status = "in_progress"

    brief_status = "ready" if (response_count > 0 or note_count > 0) else "empty"

    failure_tag_counts: Counter[str] = Counter()
    script_group_counts: Counter[str] = Counter()
    for item in representatives:
        failure_tag_counts.update(str(tag) for tag in item.get("failure_tags", []))
        script_group_counts.update(str(group) for group in item.get("input_script_groups", []))

    first_things_to_watch = _start_card_watch_items(failure_tag_counts)
    if not first_things_to_watch:
        first_things_to_watch = [
            "字間が広すぎるか",
            "長文で行全体が機械的に揃いすぎていないか",
            "Latin / digit / punctuation の混在で崩れないか",
            "反復文字が同じ形に寄りすぎていないか",
        ]

    top_representatives = [
        {
            "experiment_id": str(item.get("experiment_id", "unknown")),
            "input_text": str(item.get("input_text", "")),
            "reason": str(item.get("reason", "")),
            "marker": "failure-tag" if item.get("failure_tags") else "metric-extreme",
        }
        for item in representatives[:8]
    ]

    return {
        "sort_order": sort_order,
        "record_count": int(packet.get("record_count", len(representatives))),
        "representative_count": int(packet.get("representative_count", len(representatives))),
        "loop_status": loop_status,
        "brief_status": brief_status,
        "note_count": note_count,
        "response_count": response_count,
        "first_things_to_watch": first_things_to_watch,
        "top_failure_tags": dict(failure_tag_counts.most_common(6)),
        "top_script_groups": dict(script_group_counts.most_common(6)),
        "top_representatives": top_representatives,
        "preview_head": top_representatives,
    }


def render_human_review_start_card_markdown(card: dict[str, Any]) -> str:
    lines = [
        "# Human Review Start Card",
        "",
        f"- sort_order: `{card.get('sort_order', 'default')}`",
        f"- record_count: `{card.get('record_count', 0)}`",
        f"- representative_count: `{card.get('representative_count', 0)}`",
        f"- loop_status: `{card.get('loop_status', 'awaiting_response')}`",
        f"- brief_status: `{card.get('brief_status', 'empty')}`",
        "",
        "## First Things To Watch",
    ]
    for item in card.get("first_things_to_watch", []):
        lines.append(f"- {item}")

    top_failure_tags = card.get("top_failure_tags", {})
    if top_failure_tags:
        lines.extend(["", "## Top Failure Tags"])
        for tag, count in top_failure_tags.items():
            lines.append(f"- {tag}: `{count}`")

    top_script_groups = card.get("top_script_groups", {})
    if top_script_groups:
        lines.extend(["", "## Script Groups"])
        for group, count in top_script_groups.items():
            lines.append(f"- {group}: `{count}`")

    representatives = list(card.get("top_representatives", []))
    if representatives:
        lines.extend(["", "## Top Representatives"])
        for item in representatives:
            experiment_id = item.get("experiment_id", "unknown")
            input_text = item.get("input_text", "")
            reason = item.get("reason", "")
            marker = item.get("marker", "metric-extreme")
            lines.append(f"- {experiment_id}: {input_text} ({marker})")
            if reason:
                lines.append(f"  - reason: `{reason}`")

    preview_head = list(card.get("preview_head", []))
    if preview_head:
        lines.extend(["", "## Preview Representative Head"])
        for item in preview_head:
            experiment_id = item.get("experiment_id", "unknown")
            input_text = item.get("input_text", "")
            reason = item.get("reason", "")
            marker = item.get("marker", "metric-extreme")
            lines.append(f"- {experiment_id}: {input_text} ({marker})")
            if reason:
                lines.append(f"  - reason: `{reason}`")

    return "\n".join(lines) + "\n"


def build_human_review_comparison_sheet(packet: dict[str, Any]) -> dict[str, Any]:
    representatives = list(packet.get("representatives", []))
    failure_tag_counts = dict(packet.get("failure_tag_counts", {}))
    top_failure_tags = [
        tag
        for tag, _count in sorted(
            failure_tag_counts.items(),
            key=lambda item: (-int(item[1]), item[0]),
        )[:6]
    ]
    tagged_anchors = [
        {
            "experiment_id": str(item.get("experiment_id", "unknown")),
            "input_text": str(item.get("input_text", "")),
            "reason": str(item.get("reason", "")),
            "failure_tags": list(item.get("failure_tags", [])),
            "metrics": {
                key: item.get("metrics", {}).get(key)
                for key in (
                    "baseline_drift_mm",
                    "draw_speed_cv",
                    "mean_abs_jerk_mm_s3",
                    "repeated_char_ratio",
                    "stroke_start_spacing_cv",
                )
                if key in item.get("metrics", {})
            },
        }
        for item in representatives
        if item.get("failure_tags")
    ][:8]
    what_to_compare = _comparison_sheet_watch_items(top_failure_tags)
    if not what_to_compare:
        what_to_compare = [
            "字間が広すぎないか",
            "揺れがノイズに見えないか",
            "終筆が揃いすぎていないか",
            "フォントの焼き直しに寄りすぎていないか",
            "日本語として字間のリズムが自然か",
            "行全体の流れが硬すぎないか",
        ]
    return {
        "record_count": int(packet.get("record_count", len(representatives))),
        "representative_count": int(packet.get("representative_count", len(representatives))),
        "high_priority_tags": top_failure_tags,
        "what_to_compare": what_to_compare,
        "tagged_anchors": tagged_anchors,
    }


def render_human_review_comparison_sheet_markdown(sheet: dict[str, Any]) -> str:
    lines = [
        "# Human Review Comparison Sheet",
        "",
        f"- record_count: `{sheet.get('record_count', 0)}`",
        f"- representative_count: `{sheet.get('representative_count', 0)}`",
        "",
        "## High Priority Tags",
    ]
    for tag in sheet.get("high_priority_tags", []):
        lines.append(f"- {tag}")

    lines.extend(["", "## What to Compare"])
    for item in sheet.get("what_to_compare", []):
        lines.append(f"- {item}")

    anchors = list(sheet.get("tagged_anchors", []))
    if anchors:
        lines.extend(["", "## Tagged Anchors"])
        for item in anchors:
            experiment_id = item.get("experiment_id", "unknown")
            input_text = item.get("input_text", "")
            reason = item.get("reason", "")
            lines.append(f"### {experiment_id}")
            lines.append("")
            lines.append(f"- input_text: `{input_text}`")
            lines.append(f"- reason: `{reason}`")
            lines.append(f"- failure_tags: `{item.get('failure_tags', [])}`")
            lines.append(f"- metrics: `{item.get('metrics', {})}`")
            lines.append("")

    return "\n".join(lines) + "\n"


def build_human_review_prompt(packet: dict[str, Any]) -> dict[str, Any]:
    sheet = build_human_review_comparison_sheet(packet)
    representatives = list(packet.get("representatives", []))
    top_representatives = [
        {
            "experiment_id": str(item.get("experiment_id", "unknown")),
            "input_text": str(item.get("input_text", "")),
            "reason": str(item.get("reason", "")),
            "failure_tags": list(item.get("failure_tags", [])),
        }
        for item in representatives[:6]
    ]
    focus_questions = [
        "最初にどの代表サンプルが自然 / 不自然に見えるか",
        "字間・終筆・揺れ・フォント感のうち、何を最優先で直したいか",
        "長文、短文、Latin、数字、記号のどの混在で崩れやすいか",
        "次の改版で 1 点だけ直すなら何を選ぶか",
    ]
    response_format = [
        "良い点: 1 行で書く",
        "気になる点: 1〜3 点を書く",
        "優先修正: 1 点だけ書く",
        "必要なら代表 experiment_id を添える",
    ]
    return {
        "record_count": int(packet.get("record_count", len(representatives))),
        "representative_count": int(packet.get("representative_count", len(representatives))),
        "sort_order": str(packet.get("sort_order", "default")),
        "high_priority_tags": sheet.get("high_priority_tags", []),
        "what_to_compare": sheet.get("what_to_compare", []),
        "focus_questions": focus_questions,
        "response_format": response_format,
        "top_representatives": top_representatives,
    }


def render_human_review_prompt_markdown(prompt: dict[str, Any]) -> str:
    lines = [
        "# Human Review Prompt",
        "",
        f"- sort_order: `{prompt.get('sort_order', 'default')}`",
        f"- record_count: `{prompt.get('record_count', 0)}`",
        f"- representative_count: `{prompt.get('representative_count', 0)}`",
        "",
        "## Focus Questions",
    ]
    for item in prompt.get("focus_questions", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Response Format"])
    for item in prompt.get("response_format", []):
        lines.append(f"- {item}")

    high_priority_tags = list(prompt.get("high_priority_tags", []))
    if high_priority_tags:
        lines.extend(["", "## High Priority Tags"])
        for tag in high_priority_tags:
            lines.append(f"- {tag}")

    what_to_compare = list(prompt.get("what_to_compare", []))
    if what_to_compare:
        lines.extend(["", "## What to Compare"])
        for item in what_to_compare:
            lines.append(f"- {item}")

    top_representatives = list(prompt.get("top_representatives", []))
    if top_representatives:
        lines.extend(["", "## Representative Head"])
        for item in top_representatives:
            experiment_id = item.get("experiment_id", "unknown")
            input_text = item.get("input_text", "")
            reason = item.get("reason", "")
            lines.append(f"- {experiment_id}: {input_text}")
            if reason:
                lines.append(f"  - reason: `{reason}`")
            failure_tags = item.get("failure_tags", [])
            if failure_tags:
                lines.append(f"  - failure_tags: `{failure_tags}`")

    return "\n".join(lines) + "\n"


def build_human_review_session_feedback(packet: dict[str, Any]) -> dict[str, Any]:
    prompt = build_human_review_prompt(packet)
    representative_ids = [
        str(item.get("experiment_id", "unknown"))
        for item in list(packet.get("representatives", []))[:8]
    ]
    return {
        "sort_order": str(packet.get("sort_order", "default")),
        "record_count": int(packet.get("record_count", len(packet.get("representatives", [])))),
        "representative_count": int(packet.get("representative_count", len(packet.get("representatives", [])))),
        "high_priority_tags": list(prompt.get("high_priority_tags", [])),
        "what_to_compare": list(prompt.get("what_to_compare", [])),
        "focus_questions": list(prompt.get("focus_questions", [])),
        "reference_representative_ids": representative_ids,
        "notes": "",
    }


def render_human_review_session_feedback_markdown(session_feedback: dict[str, Any]) -> str:
    lines = [
        "# Human Review Session Feedback",
        "",
        f"- sort_order: `{session_feedback.get('sort_order', 'default')}`",
        f"- record_count: `{session_feedback.get('record_count', 0)}`",
        f"- representative_count: `{session_feedback.get('representative_count', 0)}`",
        "",
        "## Focus Questions",
    ]
    for item in session_feedback.get("focus_questions", []):
        lines.append(f"- {item}")

    high_priority_tags = list(session_feedback.get("high_priority_tags", []))
    if high_priority_tags:
        lines.extend(["", "## High Priority Tags"])
        for tag in high_priority_tags:
            lines.append(f"- {tag}")

    what_to_compare = list(session_feedback.get("what_to_compare", []))
    if what_to_compare:
        lines.extend(["", "## What to Compare"])
        for item in what_to_compare:
            lines.append(f"- {item}")

    representative_ids = list(session_feedback.get("reference_representative_ids", []))
    if representative_ids:
        lines.extend(["", "## Reference Representatives"])
        for experiment_id in representative_ids:
            lines.append(f"- {experiment_id}")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "ここに bundle 全体への FB を書く。",
            "",
            "- 良い点:",
            "- 気になる点:",
            "- 優先修正:",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _start_card_watch_items(failure_tag_counts: Counter[str]) -> list[str]:
    candidates = [
        ("spacing-too-wide", "字間が広すぎるか"),
        ("over-jittered", "揺れが情報ではなくノイズになっていないか"),
        ("terminal-too-uniform", "終筆が機械的に揃いすぎていないか"),
        ("too-font-like", "骨格がフォントの焼き直しに寄りすぎていないか"),
        ("spacing-unnatural", "文字間のリズムが日本語として不自然でないか"),
        ("line-too-mechanical", "行全体の流れが硬すぎないか"),
    ]
    watched = [label for tag, label in candidates if failure_tag_counts.get(tag, 0) > 0]
    if watched:
        return watched[:4]
    return [label for _tag, label in candidates[:4]]


def _comparison_sheet_watch_items(top_failure_tags: list[str]) -> list[str]:
    mapping = {
        "spacing-too-wide": "字間が広すぎないか",
        "over-jittered": "揺れがノイズに見えないか",
        "terminal-too-uniform": "終筆が揃いすぎていないか",
        "too-font-like": "フォントの焼き直しに寄りすぎていないか",
        "spacing-unnatural": "日本語として字間のリズムが自然か",
        "line-too-mechanical": "行全体の流れが硬すぎないか",
        "repeated-char-too-identical": "反復文字が同じ形に寄りすぎていないか",
        "too-uniform": "速度変化が単調すぎないか",
    }
    return [mapping[tag] for tag in top_failure_tags if tag in mapping]


def build_human_review_revision_brief(summary: dict[str, Any]) -> dict[str, Any]:
    note_examples = summary.get("note_examples", [])
    note_snippets = [str(item.get("notes", "")).strip() for item in note_examples if str(item.get("notes", "")).strip()]
    primary_notes = list(dict.fromkeys(note_snippets))
    reason_tag_counts = dict(summary.get("reason_tag_counts", {}))
    top_reason_tags = [
        tag
        for tag, _count in sorted(
            reason_tag_counts.items(),
            key=lambda item: (-int(item[1]), item[0]),
        )[:8]
    ]
    focus_lines: list[str] = []
    if primary_notes:
        focus_lines.append("notes の指摘をそのまま次回の修正に反映する")
    if top_reason_tags:
        focus_lines.append(f"reason_tags の上位: {top_reason_tags}")
    if not focus_lines:
        focus_lines.append("特記なし")
    return {
        "brief_status": "ready" if primary_notes or top_reason_tags else "empty",
        "note_count": int(summary.get("note_count", 0)),
        "reason_tag_counts": reason_tag_counts,
        "primary_notes": primary_notes,
        "selected_note_examples": note_examples[:8],
        "top_reason_tags": top_reason_tags,
        "focus_lines": focus_lines,
    }


def build_human_review_revision_plan(brief: dict[str, Any]) -> dict[str, Any]:
    note_examples = brief.get("selected_note_examples", [])
    note_texts = [
        str(item.get("notes", "")).strip()
        for item in note_examples
        if str(item.get("notes", "")).strip()
    ]
    reason_tags = [str(tag) for tag in brief.get("top_reason_tags", []) if str(tag).strip()]
    focus_area_counts: dict[str, int] = {}
    proposed_changes: list[dict[str, Any]] = []
    for tag in reason_tags:
        area = _revision_focus_area_from_tag(tag)
        focus_area_counts[area] = focus_area_counts.get(area, 0) + 1
        proposed_changes.extend(_revision_changes_for_tag(tag))

    for note in note_texts:
        area = _revision_focus_area_from_note(note)
        if area:
            focus_area_counts[area] = focus_area_counts.get(area, 0) + 1

    if not focus_area_counts:
        focus_area_counts["preview"] = 1

    dominant_focus_area = sorted(
        focus_area_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[0][0]
    next_experiment_hint = _revision_next_experiment_hint(dominant_focus_area, reason_tags)
    if not proposed_changes:
        proposed_changes = [
            {
                "target": dominant_focus_area,
                "parameter": "profile_id",
                "direction": "keep-compare",
                "amount_hint": None,
                "reason": "明確な reason tag がないため、同条件で別 profile を比較する",
            }
        ]

    return {
        "plan_status": "ready" if focus_area_counts else "empty",
        "brief_status": str(brief.get("brief_status", "empty")),
        "note_count": int(brief.get("note_count", 0)),
        "focus_area_counts": dict(sorted(focus_area_counts.items())),
        "dominant_focus_area": dominant_focus_area,
        "top_reason_tags": reason_tags,
        "primary_notes": list(brief.get("primary_notes", [])),
        "note_examples": note_examples[:8],
        "proposed_changes": proposed_changes,
        "next_experiment_hint": next_experiment_hint,
    }


def build_human_review_preview_revision_plan(
    brief: dict[str, Any],
    preview_proposal: dict[str, Any],
) -> dict[str, Any]:
    human_plan = build_human_review_revision_plan(brief)
    human_focus_area = str(human_plan.get("dominant_focus_area", "")).strip() or "preview"
    preview_revision_plans = list(preview_proposal.get("revision_plans", []))
    filtered_revision_plans = [
        plan for plan in preview_revision_plans if str(plan.get("focus_area", "")) == human_focus_area
    ]
    if not filtered_revision_plans:
        filtered_revision_plans = preview_revision_plans

    filtered_area_counts: dict[str, int] = {}
    for plan in filtered_revision_plans:
        area = str(plan.get("focus_area", "")) or "preview"
        filtered_area_counts[area] = filtered_area_counts.get(area, 0) + 1

    return {
        "plan_status": "ready" if filtered_revision_plans else "empty",
        "human_revision_plan": human_plan,
        "human_focus_area": human_focus_area,
        "human_next_experiment_hint": human_plan["next_experiment_hint"],
        "human_proposed_changes": list(human_plan.get("proposed_changes", [])),
        "human_primary_notes": list(human_plan.get("primary_notes", [])),
        "human_top_reason_tags": list(human_plan.get("top_reason_tags", [])),
        "preview_revision_plan": preview_proposal,
        "preview_focus_area_counts": dict(sorted(filtered_area_counts.items())),
        "preview_revision_plans": filtered_revision_plans,
        "preview_selected_candidate_count": len(filtered_revision_plans),
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


def render_human_review_revision_brief_markdown(brief: dict[str, Any]) -> str:
    lines = [
        "# Human Review Revision Brief",
        "",
        f"- brief_status: `{brief['brief_status']}`",
        f"- note_count: `{brief['note_count']}`",
        f"- top_reason_tags: `{brief['top_reason_tags']}`",
        "",
        "## Focus Lines",
        "",
    ]
    lines.extend(f"- {item}" for item in brief.get("focus_lines", []))
    lines.extend(["", "## Primary Notes", ""])
    if not brief.get("primary_notes"):
        lines.append("- none")
    else:
        for note in brief["primary_notes"]:
            lines.append(f"- {note}")
    lines.extend(["", "## Note Examples", ""])
    if not brief.get("selected_note_examples"):
        lines.append("- none")
    else:
        for note in brief["selected_note_examples"]:
            lines.append(
                "- "
                f"{note['experiment_id']}: "
                f"decision=`{note['decision']}`, "
                f"reason_tags=`{note['reason_tags']}`"
            )
            lines.append(f"  - notes: {note['notes']}")
    return "\n".join(lines) + "\n"


def render_human_review_revision_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Human Review Revision Plan",
        "",
        f"- plan_status: `{plan['plan_status']}`",
        f"- brief_status: `{plan['brief_status']}`",
        f"- note_count: `{plan['note_count']}`",
        f"- dominant_focus_area: `{plan['dominant_focus_area']}`",
        f"- focus_area_counts: `{plan['focus_area_counts']}`",
        f"- next_experiment_hint: `{plan['next_experiment_hint']}`",
        "",
        "## Proposed Changes",
        "",
    ]
    if not plan["proposed_changes"]:
        lines.append("- none")
    else:
        for change in plan["proposed_changes"]:
            lines.append(
                "- "
                f"target=`{change['target']}` "
                f"parameter=`{change['parameter']}` "
                f"direction=`{change['direction']}` "
                f"amount_hint=`{change['amount_hint']}` "
                f"reason=`{change['reason']}`"
            )
    lines.extend(["", "## Notes", ""])
    if not plan["primary_notes"]:
        lines.append("- none")
    else:
        for note in plan["primary_notes"]:
            lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def render_human_review_preview_revision_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Human Review Preview Revision Plan",
        "",
        f"- plan_status: `{plan['plan_status']}`",
        f"- human_focus_area: `{plan['human_focus_area']}`",
        f"- human_next_experiment_hint: `{plan['human_next_experiment_hint']}`",
        f"- preview_selected_candidate_count: `{plan['preview_selected_candidate_count']}`",
        f"- preview_focus_area_counts: `{plan['preview_focus_area_counts']}`",
        "",
        "## Human Revision Brief",
        "",
        render_human_review_revision_brief_markdown(plan["human_revision_plan"]).rstrip(),
        "",
        "## Human Revision Plan",
        "",
        render_human_review_revision_plan_markdown(plan["human_revision_plan"]).rstrip(),
        "",
        "## Preview Revision Proposal",
        "",
    ]
    preview_proposal = plan["preview_revision_plan"]
    if not preview_proposal.get("revision_plans"):
        lines.append("- none")
    else:
        for item in plan["preview_revision_plans"]:
            lines.extend(
                [
                    f"### input={item['input_text']} seed={item['seed']}",
                    "",
                    f"- status: `{item['status']}`",
                    f"- focus_area: `{item['focus_area']}`",
                    f"- candidate_experiment_id: `{item['candidate_experiment_id']}`",
                    f"- candidate_profile_id: `{item.get('candidate_profile_id', '')}`",
                    f"- selected_failure_tags: `{item.get('selected_failure_tags', [])}`",
                    f"- selected_next_actions: `{item.get('selected_next_actions', [])}`",
                    f"- next_experiment_hint: `{item['next_experiment_hint']}`",
                    "- proposed_changes:",
                ]
            )
            if item["proposed_changes"]:
                for change in item["proposed_changes"]:
                    lines.append(
                        "  - "
                        f"target=`{change['target']}` "
                        f"parameter=`{change['parameter']}` "
                        f"direction=`{change['direction']}` "
                        f"amount_hint=`{change['amount_hint']}` "
                        f"reason=`{change['reason']}`"
                    )
            else:
                lines.append("  - none")
            lines.append("")
    return "\n".join(lines) + "\n"


def _revision_focus_area_from_tag(tag: str) -> str:
    tag = tag.strip()
    if tag in {"plotter-unsafe"}:
        return "safety"
    if tag in {"too-font-like", "skeleton-too-rigid", "repeated-char-too-identical"}:
        return "dictionary"
    if tag in {"too-uniform", "over-jittered"}:
        return "motion"
    if tag in {"line-too-mechanical", "spacing-too-wide", "spacing-unnatural"}:
        return "layout"
    if tag in {"terminal-too-uniform"}:
        return "terminal"
    return "preview"


def _revision_focus_area_from_note(note: str) -> str:
    lowered = note.lower()
    if any(token in lowered for token in ("安全", "unsafe", "danger")):
        return "safety"
    if any(token in lowered for token in ("字間", "間隔", "行間", "layout", "spacing", "余白")):
        return "layout"
    if any(token in lowered for token in ("揺れ", "速度", "等速", "jitter", "motion", "機械的", "終筆")):
        return "motion"
    if any(token in lowered for token in ("字形", "形", "崩れ", "フォント", "骨格", "dictionary")):
        return "dictionary"
    if any(token in lowered for token in ("終端", "払い", "はね", "とめ", "terminal")):
        return "terminal"
    if any(token in lowered for token in ("preview", "見た目", "印象", "見え")):
        return "preview"
    return ""


def _revision_changes_for_tag(tag: str) -> list[dict[str, Any]]:
    change_map = {
        "too-uniform": [
            {
                "target": "motion",
                "parameter": "timing_jitter_cv",
                "direction": "increase",
                "amount_hint": 0.03,
                "reason": "等速感を減らし、速度ピークを作る",
            }
        ],
        "over-jittered": [
            {
                "target": "motion",
                "parameter": "timing_jitter_cv",
                "direction": "decrease",
                "amount_hint": 0.03,
                "reason": "揺れが強すぎるので運動を落ち着かせる",
            }
        ],
        "line-too-mechanical": [
            {
                "target": "layout",
                "parameter": "baseline_drift_mm",
                "direction": "increase",
                "amount_hint": 0.4,
                "reason": "行方向の機械的整列を崩す",
            }
        ],
        "spacing-unnatural": [
            {
                "target": "layout",
                "parameter": "spacing_mean_mm",
                "direction": "increase",
                "amount_hint": 0.15,
                "reason": "字間をわずかに広げる",
            }
        ],
        "spacing-too-wide": [
            {
                "target": "layout",
                "parameter": "spacing_mean_mm",
                "direction": "decrease",
                "amount_hint": 0.15,
                "reason": "字間を詰めて広がりすぎを抑える",
            }
        ],
        "skeleton-too-rigid": [
            {
                "target": "dictionary",
                "parameter": "shape_variation",
                "direction": "increase",
                "amount_hint": 0.02,
                "reason": "字形の剛直さを和らげる",
            }
        ],
        "repeated-char-too-identical": [
            {
                "target": "dictionary",
                "parameter": "shape_variation",
                "direction": "increase",
                "amount_hint": 0.02,
                "reason": "同一文字の見え方の差を増やす",
            }
        ],
        "terminal-too-uniform": [
            {
                "target": "profile",
                "parameter": "terminal_gains",
                "direction": "increase-contrast",
                "amount_hint": 0.1,
                "reason": "払い、はね、とめの終端差を強める",
            }
        ],
        "too-font-like": [
            {
                "target": "profile",
                "parameter": "slant_deg",
                "direction": "adjust",
                "amount_hint": 2.0,
                "reason": "字体から離して筆者寄りに寄せる",
            }
        ],
        "plotter-unsafe": [
            {
                "target": "safety",
                "parameter": "gcode_safety",
                "direction": "fix",
                "amount_hint": None,
                "reason": "安全性違反を解消してから再比較する",
            }
        ],
    }
    return list(change_map.get(tag, []))


def _revision_next_experiment_hint(focus_area: str, tags: list[str]) -> str:
    if "plotter-unsafe" in tags:
        return "G-code safety を直してから同じ input / seed で再評価する"
    if focus_area == "motion":
        return "同じ input / seed で motion profile を上げて再生成する"
    if focus_area == "layout":
        return "同じ input / seed で layout spacing と baseline drift を調整する"
    if focus_area == "dictionary":
        return "同じ input / seed で dictionary の shape variation を増やして再生成する"
    if focus_area == "profile":
        return "同じ input / seed で別 profile を適用して再生成する"
    return "同じ input / seed で preview 比較を継続する"

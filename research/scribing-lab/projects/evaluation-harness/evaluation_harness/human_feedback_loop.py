from __future__ import annotations

from typing import Any

from evaluation_harness.human_review import (
    build_human_review_packet,
    render_human_review_packet_markdown,
)
from evaluation_harness.human_review_response import (
    DECISIONS,
    HumanReviewResponse,
    build_human_review_revision_brief,
    summarize_human_review_agreement,
    summarize_human_review_calibration,
    load_human_review_responses,
    render_human_review_response_markdown,
    render_human_review_revision_brief_markdown,
    summarize_human_review_responses,
)
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import NEXT_ACTIONS


REVIEW_AXES: tuple[dict[str, str | tuple[str, ...]], ...] = (
    {
        "name": "readability",
        "description": "読めるか、文字が小さすぎないか、欠落や反転がないかを確認する",
        "reason_tags": ("too-small", "glyph-orientation-odd"),
    },
    {
        "name": "layout",
        "description": "字間、行間、配置が空きすぎていないかを確認する",
        "reason_tags": ("spacing-too-wide", "spacing-unnatural"),
    },
    {
        "name": "shape",
        "description": "特定の文字だけが明らかに異常でないかを確認する",
        "reason_tags": ("skeleton-too-rigid", "too-font-like"),
    },
    {
        "name": "motion",
        "description": "動きが等速すぎず、終筆が硬すぎず、機械的すぎないかを確認する",
        "reason_tags": ("too-uniform", "line-too-mechanical", "terminal-too-uniform"),
    },
    {
        "name": "consistency",
        "description": "同じ文字や反復表現が不自然に同一化していないかを確認する",
        "reason_tags": ("repeated-char-too-identical",),
    },
)

REVIEW_CHECKLIST: tuple[str, ...] = (
    "preview を先に見る。",
    "読めるか、字が小さすぎないかを確認する。",
    "字間が空きすぎていないかを確認する。",
    "特定の文字だけがひっくり返ったり崩れたりしていないかを確認する。",
    "等速で機械的に見えないかを確認する。",
    "判定には accept / reject / needs-tuning を使う。",
)

ALLOWED_REASON_TAGS: tuple[str, ...] = tuple(sorted(NEXT_ACTIONS))


def build_human_review_response_template(
    packet: dict[str, Any],
    *,
    reviewer_id: str = "",
) -> dict[str, Any]:
    return {
        "reviewer_id": reviewer_id,
        "representative_count": int(packet.get("representative_count", 0)),
        "allowed_decisions": sorted(DECISIONS),
        "allowed_reason_tags": list(ALLOWED_REASON_TAGS),
        "review_axes": [
            {
                "name": item["name"],
                "description": item["description"],
                "reason_tags": list(item["reason_tags"]),
            }
            for item in REVIEW_AXES
        ],
        "checklist": list(REVIEW_CHECKLIST),
        "responses": [
            _template_response_item(item, reviewer_id=reviewer_id)
            for item in packet.get("representatives", [])
        ],
    }


def build_human_feedback_loop(
    records: list[ExperimentRecord],
    *,
    responses_data: Any | None = None,
    reviewer_id: str = "",
    target_count: int | None = None,
) -> dict[str, Any]:
    packet = build_human_review_packet(records, target_count=target_count)
    template = build_human_review_response_template(packet, reviewer_id=reviewer_id)
    response_summary = None
    calibration_summary = None
    agreement_summary = None
    if responses_data is not None:
        responses = load_human_review_responses(responses_data)
        response_summary = summarize_human_review_responses(packet, responses)
        calibration_summary = summarize_human_review_calibration(packet, responses)
        agreement_summary = summarize_human_review_agreement(responses)
    revision_brief = build_human_review_revision_brief(response_summary or {
        "note_count": 0,
        "reason_tag_counts": {},
        "note_examples": [],
    })

    loop_status = _loop_status(response_summary)
    next_actions = _next_actions(loop_status, response_summary, calibration_summary, agreement_summary)
    return {
        "loop_status": loop_status,
        "packet": packet,
        "response_template": template,
        "response_summary": response_summary,
        "calibration_summary": calibration_summary,
        "agreement_summary": agreement_summary,
        "revision_brief": revision_brief,
        "next_actions": next_actions,
    }


def summarize_human_review_draft_rows(
    packet: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize partially completed human review rows for an interactive UI."""

    responses: list[HumanReviewResponse] = []
    validation_errors: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for row in rows:
        experiment_id = str(row.get("experiment_id", "")).strip()
        if not experiment_id:
            validation_errors.append("missing experiment_id")
            continue
        if experiment_id in seen_ids:
            duplicate_ids.add(experiment_id)
            continue
        seen_ids.add(experiment_id)

        decision = str(row.get("decision", "")).strip()
        if not decision:
            validation_errors.append(f"missing decision: {experiment_id}")
            continue

        reason_tags = [str(tag).strip() for tag in row.get("reason_tags", []) if str(tag).strip()]
        notes = str(row.get("notes", ""))
        reviewer_id = str(row.get("reviewer_id", ""))
        try:
            responses.append(
                HumanReviewResponse(
                    experiment_id=experiment_id,
                    decision=decision,
                    reason_tags=reason_tags,
                    notes=notes,
                    reviewer_id=reviewer_id,
                )
            )
        except ValueError as exc:
            validation_errors.append(f"{experiment_id}: {exc}")

    summary = summarize_human_review_responses(packet, responses)
    summary["validation_errors"] = sorted(
        {
            *summary["validation_errors"],
            *validation_errors,
            *(f"duplicate draft: {experiment_id}" for experiment_id in sorted(duplicate_ids)),
        }
    )
    summary["can_proceed_to_plot"] = (
        not summary["validation_errors"]
        and summary["decision_counts"].get("reject", 0) == 0
        and summary["decision_counts"].get("needs-tuning", 0) == 0
        and summary["decision_counts"].get("accept", 0) == len(
            {
                str(item["experiment_id"])
                for item in packet.get("representatives", [])
            }
        )
    )
    return summary


def render_human_review_response_template_markdown(template: dict[str, Any]) -> str:
    lines = [
        "# Human Review Response Template",
        "",
        f"- reviewer_id: `{template['reviewer_id']}`",
        f"- representative_count: `{template['representative_count']}`",
        f"- allowed_decisions: `{template['allowed_decisions']}`",
        f"- allowed_reason_tags: `{template['allowed_reason_tags']}`",
        "",
        "## Review Axes",
        "",
    ]
    for axis in template["review_axes"]:
        lines.extend(
            [
                f"- {axis['name']}: `{axis['description']}`",
                f"  - reason_tags: `{axis['reason_tags']}`",
            ]
        )
    lines.extend(["", "## Checklist", ""])
    lines.extend(f"- {item}" for item in template["checklist"])
    lines.extend(["", "## Response Slots", ""])
    if not template["responses"]:
        lines.append("- none")
    for item in template["responses"]:
        lines.extend(
            [
                f"### {item['experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- input_script_groups: `{item.get('input_script_groups', [])}`",
                f"- seed: `{item['seed']}`",
                f"- preview: `{item['preview']}`",
                f"- failure_tags: `{item['failure_tags']}`",
                f"- metrics: `{item['metrics']}`",
                "- decision: `accept / reject / needs-tuning`",
                "- reason_tags: `[]`",
                "- notes: `optional`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_human_feedback_loop_markdown(loop: dict[str, Any]) -> str:
    lines = [
        "# Human Feedback Loop",
        "",
        f"- loop_status: `{loop['loop_status']}`",
        f"- representative_count: `{loop['packet']['representative_count']}`",
        f"- record_count: `{loop['packet']['record_count']}`",
        f"- next_actions: `{loop['next_actions']}`",
        "",
        "## Review Packet",
        "",
        render_human_review_packet_markdown(loop["packet"]).rstrip(),
        "",
        "## Response Template",
        "",
        render_human_review_response_template_markdown(loop["response_template"]).rstrip(),
        "",
    ]
    if loop["response_summary"] is not None:
        lines.extend(
            [
                "## Response Summary",
                "",
                render_human_review_response_markdown(loop["response_summary"]).rstrip(),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Response Summary",
                "",
                "- pending",
                "",
            ]
        )
    lines.extend(
        [
            "## Revision Brief",
            "",
            render_human_review_revision_brief_markdown(loop["revision_brief"]).rstrip(),
            "",
        ]
    )
    if loop.get("calibration_summary") is not None:
        lines.extend(
            [
                "## Calibration Summary",
                "",
                f"- reviewed_response_count: `{loop['calibration_summary']['reviewed_response_count']}`",
                f"- reason_tag_alignment: `{loop['calibration_summary']['reason_tag_alignment']}`",
                f"- overtriggered_tags: `{loop['calibration_summary']['overtriggered_tags']}`",
                f"- supported_tags: `{loop['calibration_summary']['supported_tags']}`",
                f"- uncertain_tags: `{loop['calibration_summary']['uncertain_tags']}`",
                f"- recommended_adjustments: `{loop['calibration_summary']['recommended_adjustments']}`",
                "",
            ]
        )
    if loop.get("agreement_summary") is not None:
        lines.extend(
            [
                "## Agreement Summary",
                "",
                f"- reviewer_count: `{loop['agreement_summary']['reviewer_count']}`",
                f"- overlapping_item_count: `{loop['agreement_summary']['overlapping_item_count']}`",
                f"- mean_cohen_kappa: `{loop['agreement_summary']['mean_cohen_kappa']}`",
                f"- mean_reason_tag_jaccard: `{loop['agreement_summary']['mean_reason_tag_jaccard']}`",
                f"- pairwise_kappas: `{loop['agreement_summary']['pairwise_kappas']}`",
                "",
            ]
        )
    lines.extend(["## Next Actions", ""])
    if loop["next_actions"]:
        lines.extend(f"- {item}" for item in loop["next_actions"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _template_response_item(item: dict[str, Any], *, reviewer_id: str) -> dict[str, Any]:
    return {
        "experiment_id": item["experiment_id"],
        "input_text": item["input_text"],
        "input_script_groups": list(item.get("input_script_groups", [])),
        "seed": item["seed"],
        "preview": item["preview"],
        "failure_tags": list(item["failure_tags"]),
        "metrics": dict(item["metrics"]),
        "decision": "",
        "reason_tags": [],
        "notes": "",
        "reviewer_id": reviewer_id,
    }


def _loop_status(response_summary: dict[str, Any] | None) -> str:
    if response_summary is None:
        return "awaiting_response"
    if response_summary["validation_errors"]:
        return "needs_response_fix"
    if response_summary["can_proceed_to_plot"]:
        return "ready_for_plot"
    return "needs_tuning"


def _next_actions(
    loop_status: str,
    response_summary: dict[str, Any] | None,
    calibration_summary: dict[str, Any] | None = None,
    agreement_summary: dict[str, Any] | None = None,
) -> list[str]:
    if loop_status == "awaiting_response":
        return [
            "response_template を埋めて human review responses を作成する",
            "responses_json を validate-human-review に通す",
        ]
    if response_summary is None:
        return []
    if loop_status == "needs_response_fix":
        return [
            "unknown / missing / duplicate response を修正する",
            "representative ids と responses を一致させる",
        ] + list(response_summary["validation_errors"])
    if loop_status == "ready_for_plot":
        return [
            "plot-ready-packet を作成して plot 前確認へ進む",
        ]

    reason_tags = _collect_reason_tags(response_summary)
    actions: list[str] = []
    for tag in reason_tags:
        action = NEXT_ACTIONS.get(tag)
        if action and action not in actions:
            actions.append(action)
    if not actions:
        actions.append("reason_tags を踏まえて generator / layout / motion を調整する")

    if calibration_summary is not None:
        for item in calibration_summary.get("recommended_adjustments", []):
            if item not in actions:
                actions.append(item)
    if agreement_summary is not None and agreement_summary.get("mean_cohen_kappa", 0.0) < 0.4:
        low_agreement_action = "reviewers の判定基準をすり合わせて low-agreement item を再レビューする"
        if low_agreement_action not in actions:
            actions.append(low_agreement_action)
    note_count = int(response_summary.get("note_count", 0))
    if note_count > 0:
        note_action = "notes に書かれた違和感を次回の修正にそのまま反映する"
        if note_action not in actions:
            actions.append(note_action)
    return actions


def _collect_reason_tags(response_summary: dict[str, Any]) -> list[str]:
    tags = sorted(
        {
            str(tag)
            for response in response_summary.get("responses", [])
            if response.get("decision") != "accept"
            for tag in response.get("reason_tags", [])
        }
    )
    return tags

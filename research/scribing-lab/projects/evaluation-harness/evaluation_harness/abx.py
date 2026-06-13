from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from collections import defaultdict
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation_harness.compare import _focus_area_from_tags, _next_experiment_hint, _proposed_changes_for_tags
from evaluation_harness.structure_motion import run_structure_motion
from evaluation_harness.writer_profile import build_revision_profile, resolve_writer_profile
from evaluation_harness.registry import ExperimentRegistry


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


def load_abx_responses(data: Any) -> list[AbxResponse]:
    raw_responses = data.get("responses", []) if isinstance(data, dict) else data
    if raw_responses is None:
        raw_responses = []

    responses: list[AbxResponse] = []
    for item in raw_responses:
        responses.append(
            AbxResponse(
                item_id=str(item.get("item_id", "")).strip(),
                evaluator_id=str(item.get("evaluator_id", "")).strip(),
                choice=str(item.get("choice", "")).strip(),
                confidence=int(item.get("confidence", 0)),
                note=str(item.get("note", "")),
            )
        )
    return responses


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


def build_abx_response_template(
    packet: dict[str, Any],
    *,
    evaluator_id: str = "",
) -> dict[str, Any]:
    return {
        "evaluator_id": evaluator_id,
        "item_count": len(packet.get("abx_items", [])),
        "allowed_choices": ["A", "B", "tie"],
        "confidence_scale": [1, 2, 3, 4, 5],
        "checklist": [
            "preview を先に見る。",
            "どちらが人間の手書きに近いかを 1 つ選ぶ。",
            "迷う場合は tie を使う。",
            "確信度は 1 から 5 で記録する。",
        ],
        "responses": [
            _abx_template_response_item(item, evaluator_id=evaluator_id)
            for item in packet.get("abx_items", [])
        ],
    }


def build_human_abx_feedback_loop(
    packet: dict[str, Any],
    *,
    responses_data: Any | None = None,
    evaluator_id: str = "",
    max_items: int | None = None,
) -> dict[str, Any]:
    packet = _limit_abx_packet(packet, max_items=max_items)
    template = build_abx_response_template(packet, evaluator_id=evaluator_id)
    response_summary = None
    if responses_data is not None:
        responses = load_abx_responses(responses_data)
        items = _abx_items_for_response_ids(packet, responses)
        response_summary = summarize_abx_responses(
            responses,
            items=items,
        )

    loop_status = _abx_loop_status(response_summary)
    next_actions = _abx_next_actions(response_summary)
    return {
        "loop_status": loop_status,
        "packet": packet,
        "response_template": template,
        "response_summary": response_summary,
        "next_actions": next_actions,
    }


def build_abx_workbook(
    packet: dict[str, Any],
    *,
    responses_data: Any | None = None,
    evaluator_id: str = "",
    max_items: int | None = None,
) -> dict[str, Any]:
    feedback_loop = build_human_abx_feedback_loop(
        packet,
        responses_data=responses_data,
        evaluator_id=evaluator_id,
        max_items=max_items,
    )
    responses = load_abx_responses(responses_data) if responses_data is not None else []
    response_by_item = {response.item_id: response for response in responses}
    rows = [
        _abx_workbook_row(item, response_by_item.get(str(item.get("item_id", ""))))
        for item in feedback_loop["packet"].get("abx_items", [])
    ]
    completed_row_count, pending_row_count, completion_ratio = summarize_abx_workbook_completion(
        {"rows": rows}
    )
    return {
        "loop_status": feedback_loop["loop_status"],
        "next_actions": list(feedback_loop["next_actions"]),
        "packet": feedback_loop["packet"],
        "response_template": feedback_loop["response_template"],
        "rows": rows,
        "completed_row_count": completed_row_count,
        "pending_row_count": pending_row_count,
        "completion_ratio": completion_ratio,
    }


def summarize_abx_workbook_completion(workbook: dict[str, Any]) -> tuple[int, int, float]:
    rows = list(workbook.get("rows", []))
    completed_row_count = sum(
        1
        for row in rows
        if str(row.get("choice", "")).strip() and str(row.get("confidence", "")).strip()
    )
    pending_row_count = len(rows) - completed_row_count
    completion_ratio = round(completed_row_count / len(rows), 4) if rows else 0.0
    return completed_row_count, pending_row_count, completion_ratio


def build_abx_pending_packet(packet: dict[str, Any], workbook: dict[str, Any]) -> dict[str, Any]:
    pending_item_ids = {
        str(row.get("item_id", ""))
        for row in workbook.get("rows", [])
        if not str(row.get("choice", "")).strip() or not str(row.get("confidence", "")).strip()
    }
    pending_items: list[dict[str, Any]] = []
    for item in packet.get("abx_items", []):
        if str(item.get("item_id", "")) not in pending_item_ids:
            continue
        pending_items.append(
            {
                **item,
                "baseline_experiment_id": item.get("baseline_experiment_id", ""),
                "candidate_experiment_id": item.get("candidate_experiment_id", ""),
                "candidate_profile_id": item.get("candidate_profile_id", ""),
                "expected_preference": item.get("expected_preference"),
                "selected_failure_tags": list(item.get("selected_failure_tags", [])),
                "selected_next_actions": list(item.get("selected_next_actions", [])),
                "focus_area": item.get("focus_area", "") or _focus_area_from_actions(item.get("selected_next_actions", [])),
                "selection_status": item.get("selection_status", "pending"),
                "option_a_artifact": item.get("option_a_artifact", ""),
                "option_b_artifact": item.get("option_b_artifact", ""),
            }
        )
    selected_profile_counts: dict[str, int] = {}
    for item in pending_items:
        profile_id = str(item.get("candidate_profile_id", "")).strip()
        if profile_id:
            selected_profile_counts[profile_id] = selected_profile_counts.get(profile_id, 0) + 1
    selected_next_actions = [
        action
        for item in pending_items
        for action in item.get("selected_next_actions", [])
    ]
    focus_area_counts: dict[str, int] = {}
    for item in pending_items:
        focus_area = str(item.get("focus_area", "")).strip()
        if focus_area:
            focus_area_counts[focus_area] = focus_area_counts.get(focus_area, 0) + 1
    return {
        **packet,
        "abx_items": pending_items,
        "record_count": packet.get("record_count", len(packet.get("abx_items", []))),
        "expected_group_count": packet.get("expected_group_count", len(pending_items)),
        "selected_candidate_count": len(pending_items),
        "selected_coverage_ratio": packet.get("selected_coverage_ratio", 0.0),
        "selected_profile_counts": selected_profile_counts,
        "candidate_profile_counts": packet.get("candidate_profile_counts", {}),
        "focus_area_counts": packet.get("focus_area_counts", focus_area_counts),
        "recommended_action_counts": packet.get("recommended_action_counts", {}),
        "pending_item_ids": sorted(pending_item_ids),
        "pending_item_count": len(pending_items),
        "pending_selected_candidate_count": len(pending_items),
        "packet_focus_areas": packet.get("packet_focus_areas", []),
        "packet_max_items": packet.get("packet_max_items", None),
        "source_selected_candidate_count": packet.get(
            "source_selected_candidate_count",
            packet.get("selected_candidate_count", len(packet.get("abx_items", []))),
        ),
    }


def _limit_abx_packet(packet: dict[str, Any], *, max_items: int | None) -> dict[str, Any]:
    if max_items is None or max_items <= 0:
        return packet

    items = list(packet.get("abx_items", []))
    if len(items) <= max_items:
        return packet

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get("candidate_profile_id", ""))].append(item)

    ordered_profiles = sorted(grouped, key=lambda profile_id: (-len(grouped[profile_id]), profile_id))
    reduced: list[dict[str, Any]] = []
    while len(reduced) < max_items:
        progressed = False
        for profile_id in ordered_profiles:
            bucket = grouped[profile_id]
            if not bucket:
                continue
            reduced.append(bucket.pop(0))
            progressed = True
            if len(reduced) >= max_items:
                break
        if not progressed:
            break

    return {**packet, "abx_items": reduced}


def render_abx_response_template_markdown(template: dict[str, Any]) -> str:
    lines = [
        "# ABX Response Template",
        "",
        f"- evaluator_id: `{template['evaluator_id']}`",
        f"- item_count: `{template['item_count']}`",
        f"- allowed_choices: `{template['allowed_choices']}`",
        f"- confidence_scale: `{template['confidence_scale']}`",
        "",
        "## Checklist",
        "",
    ]
    lines.extend(f"- {item}" for item in template["checklist"])
    lines.extend(["", "## Response Slots", ""])
    if not template["responses"]:
        lines.append("- none")
    for item in template["responses"]:
        lines.extend(
            [
                f"### {item['item_id']}",
                "",
                f"- prompt: `{item['prompt']}`",
                f"- question: `{item['question']}`",
                f"- candidate_profile_id: `{item['candidate_profile_id']}`",
                f"- baseline_experiment_id: `{item['baseline_experiment_id']}`",
                f"- candidate_experiment_id: `{item['candidate_experiment_id']}`",
                f"- selected_failure_tags: `{item['selected_failure_tags']}`",
                f"- selected_next_actions: `{item['selected_next_actions']}`",
                f"- choice: `A / B / tie`",
                f"- confidence: `1 .. 5`",
                f"- note: `optional`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_abx_feedback_loop_markdown(loop: dict[str, Any]) -> str:
    packet = loop["packet"]
    lines = [
        "# ABX Feedback Loop",
        "",
        f"- loop_status: `{loop['loop_status']}`",
        f"- next_actions: `{loop['next_actions']}`",
        "",
        "## Packet",
        "",
        f"- item_count: `{len(packet.get('abx_items', []))}`",
        f"- selected_candidate_count: `{packet.get('selected_candidate_count', 0)}`",
        f"- selected_profile_counts: `{packet.get('selected_profile_counts', {})}`",
        "",
        "### Items",
        "",
    ]
    if not packet.get("abx_items"):
        lines.append("- none")
    for item in packet.get("abx_items", []):
        lines.append(
            "- "
            f"{item.get('item_id', '')}: "
            f"prompt=`{item.get('prompt', '')}`, "
            f"candidate_profile_id=`{item.get('candidate_profile_id', '')}`, "
            f"selected_failure_tags=`{item.get('selected_failure_tags', [])}`"
        )
    lines.extend(
        [
            "",
            "## Response Template",
            "",
            render_abx_response_template_markdown(loop["response_template"]).rstrip(),
            "",
        ]
    )
    if loop["response_summary"] is not None:
        lines.extend(
            [
                "## Response Summary",
                "",
                render_abx_summary_markdown(loop["response_summary"]).rstrip(),
                "",
            ]
        )
    else:
        lines.extend(["## Response Summary", "", "- pending", ""])
    return "\n".join(lines) + "\n"


def render_abx_workbook_markdown(workbook: dict[str, Any]) -> str:
    completed_row_count, pending_row_count, completion_ratio = summarize_abx_workbook_completion(workbook)
    lines = [
        "# ABX Workbook",
        "",
        f"- loop_status: `{workbook['loop_status']}`",
        f"- next_actions: `{workbook['next_actions']}`",
        f"- row_count: `{len(workbook.get('rows', []))}`",
        f"- completed_row_count: `{completed_row_count}`",
        f"- pending_row_count: `{pending_row_count}`",
        f"- completion_ratio: `{completion_ratio}`",
        "",
        "## Instructions",
        "",
        "- preview を先に見る。",
        "- 各 row について、A/B/tie と confidence を埋める。",
        "- note には、違和感の理由を短く書く。",
        "",
        "## Rows",
        "",
    ]
    if not workbook.get("rows"):
        lines.append("- none")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| item_id | prompt | candidate_profile_id | selected_failure_tags | selected_next_actions | choice | confidence | note |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in workbook["rows"]:
        lines.append(
            "| "
            f"{_markdown_cell(row['item_id'])} | "
            f"{_markdown_cell(row['prompt'])} | "
            f"{_markdown_cell(row['candidate_profile_id'])} | "
            f"{_markdown_cell(', '.join(row['selected_failure_tags']))} | "
            f"{_markdown_cell(', '.join(row['selected_next_actions']))} | "
            f"{_markdown_cell(row['choice'])} | "
            f"{_markdown_cell(str(row['confidence']))} | "
            f"{_markdown_cell(row['note'])} |"
        )
    return "\n".join(lines) + "\n"


def build_abx_responses_from_workbook(workbook: dict[str, Any]) -> dict[str, Any]:
    responses = []
    for row in workbook.get("rows", []):
        choice = str(row.get("choice", "")).strip()
        confidence_raw = row.get("confidence", "")
        if not choice:
            continue
        if confidence_raw in ("", None):
            continue
        responses.append(
            AbxResponse(
                item_id=str(row.get("item_id", "")),
                evaluator_id=str(workbook.get("evaluator_id", "")),
                choice=choice,
                confidence=int(confidence_raw),
                note=str(row.get("note", "")),
            ).to_dict()
        )
    return {
        "evaluator_id": workbook.get("evaluator_id", ""),
        "responses": responses,
    }


def build_abx_revision_plan(loop: dict[str, Any]) -> dict[str, Any]:
    packet = loop["packet"]
    responses = _abx_responses_from_loop(loop)
    response_by_item = {response.item_id: response for response in responses}
    item_rows: list[dict[str, Any]] = []
    focus_area_counts: Counter[str] = Counter()
    next_experiment_hints: set[str] = set()

    for item in packet.get("abx_items", []):
        item_id = str(item.get("item_id", ""))
        if responses and item_id not in response_by_item:
            continue
        tags = list(item.get("selected_failure_tags", []))
        focus_area = _focus_area_from_actions(item.get("selected_next_actions", [])) or _focus_area_from_tags(tags)
        proposed_changes = _proposed_changes_for_tags(tags, focus_area)
        next_experiment_hint = _next_experiment_hint(focus_area, tags)
        focus_area_counts[focus_area] += 1
        next_experiment_hints.add(next_experiment_hint)
        item_rows.append(
            {
                "item_id": item_id,
                "prompt": item.get("prompt", ""),
                "candidate_profile_id": item.get("candidate_profile_id", ""),
                "focus_area": focus_area,
                "selected_failure_tags": tags,
                "selected_next_actions": list(item.get("selected_next_actions", [])),
                "proposed_changes": proposed_changes,
                "next_experiment_hint": next_experiment_hint,
            }
        )

    if not item_rows:
        item_rows.append(
            {
                "item_id": "",
                "prompt": "",
                "candidate_profile_id": "",
                "focus_area": "preview",
                "selected_failure_tags": [],
                "selected_next_actions": [],
                "proposed_changes": [],
                "next_experiment_hint": "ABX responses を収集する",
            }
        )
        next_experiment_hints.add("ABX responses を収集する")

    return {
        "loop_status": loop.get("loop_status", "pending"),
        "response_count": len(responses),
        "selected_item_count": len(item_rows),
        "focus_area_counts": dict(sorted(focus_area_counts.items())),
        "next_experiment_hints": sorted(next_experiment_hints),
        "items": item_rows,
    }


def run_abx_revision_loop(
    root: str | Any,
    *,
    feedback_loop: dict[str, Any],
    baseline_generator: str = "baseline-outline",
) -> dict[str, Any]:
    root_path = Path(root)
    registry = ExperimentRegistry(root_path / "registry.jsonl")
    before_records = registry.load_all()
    before_by_id = {record.experiment_id: record for record in before_records}
    reserved_experiment_ids = {record.experiment_id for record in before_records}
    plan = build_abx_revision_plan(feedback_loop)
    applications: list[dict[str, Any]] = []
    rerun_records = []
    preview_changed_count = 0

    for item in plan["items"]:
        if not item["proposed_changes"]:
            applications.append(
                {
                    "item_id": item["item_id"],
                    "status": "no-proposed-changes",
                    "revision_experiment_id": "",
                    "revision_profile_id": "",
                    "applied_changes": [],
                    "unapplied_changes": [],
                }
            )
            continue

        source_item = _find_packet_item(feedback_loop, item["item_id"])
        if source_item is None:
            applications.append(
                {
                    "item_id": item["item_id"],
                    "status": "missing-source",
                    "revision_experiment_id": "",
                    "revision_profile_id": "",
                    "applied_changes": [],
                    "unapplied_changes": list(item["proposed_changes"]),
                }
            )
            continue

        candidate_experiment_id = str(source_item.get("candidate_experiment_id", ""))
        candidate_record = before_by_id.get(candidate_experiment_id)
        if candidate_record is None:
            applications.append(
                {
                    "item_id": item["item_id"],
                    "status": "missing-candidate-record",
                    "revision_experiment_id": "",
                    "revision_profile_id": "",
                    "applied_changes": [],
                    "unapplied_changes": list(item["proposed_changes"]),
                }
            )
            continue

        candidate_profile = resolve_writer_profile(candidate_record.profile_id)
        revision_profile_id = f"{candidate_profile.profile_id}-abx-{candidate_record.seed:03d}"
        revision = build_revision_profile(
            candidate_profile,
            list(item["proposed_changes"]),
            revision_profile_id=revision_profile_id,
            created_from_experiment=candidate_record.experiment_id,
        )
        if not revision["applied_changes"]:
            applications.append(
                {
                    "item_id": item["item_id"],
                    "status": "no-applicable-changes",
                    "candidate_experiment_id": candidate_record.experiment_id,
                    "revision_experiment_id": "",
                    "revision_profile_id": revision["profile"].profile_id,
                    "applied_changes": [],
                    "unapplied_changes": list(revision["unapplied_changes"]),
                }
            )
            continue

        experiment_id = _unique_revision_experiment_id(
            f"abx-{candidate_record.experiment_id}-rev",
            reserved_experiment_ids,
        )
        record = run_structure_motion(
            root=root_path,
            experiment_id=experiment_id,
            input_text=source_item.get("prompt", ""),
            seed=candidate_record.seed,
            writer_profile=revision["profile"],
        )
        reserved_experiment_ids.add(record.experiment_id)
        rerun_records.append(record)
        preview_before = _file_sha256(candidate_record.artifacts.get("preview", ""))
        preview_after = _file_sha256(record.artifacts.get("preview", ""))
        preview_changed = preview_before is not None and preview_after is not None and preview_before != preview_after
        if preview_changed:
            preview_changed_count += 1
        applications.append(
            {
                "item_id": item["item_id"],
                "status": "rerun",
                "candidate_experiment_id": candidate_record.experiment_id,
                "revision_experiment_id": record.experiment_id,
                "revision_profile_id": record.profile_id,
                "applied_changes": list(revision["applied_changes"]),
                "unapplied_changes": list(revision["unapplied_changes"]),
                "preview_changed": preview_changed,
                "preview_before": candidate_record.artifacts.get("preview", ""),
                "preview": record.artifacts.get("preview", ""),
                "report": record.artifacts.get("report", ""),
            }
        )

    after_records = registry.load_all()
    return {
        "baseline_generator": baseline_generator,
        "before_record_count": len(before_records),
        "after_record_count": len(after_records),
        "revision_plan": plan,
        "applications": applications,
        "rerun_count": len(rerun_records),
        "preview_changed_count": preview_changed_count,
    }


def render_abx_revision_run_markdown(run: dict[str, Any]) -> str:
    lines = [
        "# ABX Revision Run",
        "",
        f"- baseline_generator: `{run['baseline_generator']}`",
        f"- before_record_count: `{run['before_record_count']}`",
        f"- after_record_count: `{run['after_record_count']}`",
        f"- rerun_count: `{run['rerun_count']}`",
        f"- preview_changed_count: `{run['preview_changed_count']}`",
        "",
        "## Revision Plan",
        "",
        render_abx_revision_plan_markdown(run["revision_plan"]).rstrip(),
        "",
        "## Applications",
        "",
    ]
    if not run["applications"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for item in run["applications"]:
        lines.extend(
            [
                f"### {item.get('item_id', 'pending')}",
                "",
                f"- status: `{item.get('status', '')}`",
                f"- candidate_experiment_id: `{item.get('candidate_experiment_id', '')}`",
                f"- revision_experiment_id: `{item.get('revision_experiment_id', '')}`",
                f"- revision_profile_id: `{item.get('revision_profile_id', '')}`",
                f"- applied_changes: `{item.get('applied_changes', [])}`",
                f"- unapplied_changes: `{item.get('unapplied_changes', [])}`",
                f"- preview_changed: `{item.get('preview_changed', False)}`",
            ]
        )
        if item.get("preview_before"):
            lines.append(f"- preview_before: `{item['preview_before']}`")
        if item.get("preview"):
            lines.append(f"- preview: `{item['preview']}`")
        if item.get("report"):
            lines.append(f"- report: `{item['report']}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_abx_revision_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# ABX Revision Plan",
        "",
        f"- loop_status: `{plan['loop_status']}`",
        f"- response_count: `{plan['response_count']}`",
        f"- selected_item_count: `{plan['selected_item_count']}`",
        f"- focus_area_counts: `{plan['focus_area_counts']}`",
        f"- next_experiment_hints: `{plan['next_experiment_hints']}`",
        "",
        "## Items",
        "",
    ]
    if not plan["items"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for item in plan["items"]:
        lines.extend(
            [
                f"### {item['item_id'] or 'pending'}",
                "",
                f"- prompt: `{item['prompt']}`",
                f"- candidate_profile_id: `{item['candidate_profile_id']}`",
                f"- focus_area: `{item['focus_area']}`",
                f"- selected_failure_tags: `{item['selected_failure_tags']}`",
                f"- selected_next_actions: `{item['selected_next_actions']}`",
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


def _abx_template_response_item(item: dict[str, Any], *, evaluator_id: str) -> dict[str, Any]:
    return {
        "item_id": item["item_id"],
        "evaluator_id": evaluator_id,
        "prompt": item["prompt"],
        "question": item["question"],
        "candidate_profile_id": item.get("candidate_profile_id", ""),
        "baseline_experiment_id": item.get("baseline_experiment_id", ""),
        "candidate_experiment_id": item.get("candidate_experiment_id", ""),
        "selected_failure_tags": list(item.get("selected_failure_tags", [])),
        "selected_next_actions": list(item.get("selected_next_actions", [])),
    }


def _abx_workbook_row(item: dict[str, Any], response: AbxResponse | None) -> dict[str, Any]:
    return {
        "item_id": item.get("item_id", ""),
        "prompt": item.get("prompt", ""),
        "candidate_profile_id": item.get("candidate_profile_id", ""),
        "selected_failure_tags": list(item.get("selected_failure_tags", [])),
        "selected_next_actions": list(item.get("selected_next_actions", [])),
        "choice": response.choice if response is not None else "",
        "confidence": response.confidence if response is not None else "",
        "note": response.note if response is not None else "",
    }


def _abx_items_from_packet(packet: dict[str, Any]) -> list[AbxItem]:
    return [
        AbxItem(
            item_id=str(item.get("item_id", "")),
            prompt=str(item.get("prompt", "")),
            option_a_artifact=str(item.get("option_a_artifact", "")),
            option_b_artifact=str(item.get("option_b_artifact", "")),
            question=str(item.get("question", "")),
            expected_preference=item.get("expected_preference"),
        )
        for item in packet.get("abx_items", [])
    ]


def _abx_items_for_response_ids(
    packet: dict[str, Any],
    responses: list[AbxResponse],
) -> list[AbxItem]:
    packet_items = {
        str(item.get("item_id", "")): item for item in packet.get("abx_items", [])
    }
    selected_item_ids = {response.item_id for response in responses}
    return [
        _abx_item_from_packet(packet_items[item_id])
        for item_id in sorted(selected_item_ids)
        if item_id in packet_items
    ]


def _abx_responses_from_loop(loop: dict[str, Any]) -> list[AbxResponse]:
    response_summary = loop.get("response_summary")
    if not response_summary:
        return []
    response_count = int(response_summary.get("response_count", 0))
    if response_count <= 0:
        return []
    response_by_item = response_summary.get("by_item", {})
    responses: list[AbxResponse] = []
    for item_id, counts in response_by_item.items():
        for choice, count in counts.items():
            for _ in range(int(count)):
                responses.append(
                    AbxResponse(
                        item_id=str(item_id),
                        evaluator_id="",
                        choice=str(choice),
                        confidence=3,
                    )
                )
    return responses


def _find_packet_item(loop: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    for item in loop.get("packet", {}).get("abx_items", []):
        if str(item.get("item_id", "")) == item_id:
            return item
    return None


def _focus_area_from_actions(actions: list[str] | tuple[str, ...] | Any) -> str:
    text = " ".join(str(action) for action in actions)
    if not text.strip():
        return ""
    if "安全" in text or "safety" in text:
        return "safety"
    if "line spacing" in text or "character advance" in text or "字間" in text:
        return "layout"
    if "tremor" in text or "timing jitter" in text or "motion" in text:
        return "motion"
    if "shape" in text or "dictionary" in text or "字形" in text:
        return "dictionary"
    if "terminal" in text or "終端" in text:
        return "terminal"
    if "preview" in text:
        return "preview"
    return ""


def _abx_item_from_packet(item: dict[str, Any]) -> AbxItem:
    return AbxItem(
        item_id=str(item.get("item_id", "")),
        prompt=str(item.get("prompt", "")),
        option_a_artifact=str(item.get("option_a_artifact", "")),
        option_b_artifact=str(item.get("option_b_artifact", "")),
        question=str(item.get("question", "")),
        expected_preference=item.get("expected_preference"),
    )


def _file_sha256(path: str) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_revision_experiment_id(base_id: str, reserved_ids: set[str]) -> str:
    if base_id not in reserved_ids:
        return base_id
    index = 2
    while True:
        candidate = f"{base_id}-r{index:03d}"
        if candidate not in reserved_ids:
            return candidate
        index += 1


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _abx_loop_status(response_summary: dict[str, Any] | None) -> str:
    if response_summary is None:
        return "pending"
    if response_summary["duplicate_pairs"]:
        return "needs_review"
    if response_summary["tie_rate"] > 0.25:
        return "needs_review"
    if response_summary["response_count"] == 0:
        return "pending"
    return "ready"


def _abx_next_actions(response_summary: dict[str, Any] | None) -> list[str]:
    if response_summary is None:
        return ["ABX responses を収集する"]
    actions: list[str] = []
    if response_summary["duplicate_pairs"]:
        actions.append("重複応答を解消して再集計する")
    if response_summary["uncertain_items"]:
        actions.append("tie の多い item を個別に見直す")
    if response_summary["tie_rate"] > 0.25:
        actions.append("選定基準と候補差分を再確認する")
    if not actions:
        actions.append("次の preview 改善候補を選ぶ")
    return actions


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

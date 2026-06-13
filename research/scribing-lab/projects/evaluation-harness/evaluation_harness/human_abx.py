from __future__ import annotations

from typing import Any

from evaluation_harness.abx import (
    AbxItem,
    build_abx_response_template,
    build_human_abx_feedback_loop,
    load_abx_responses,
    _focus_area_from_actions,
    _focus_area_from_tags,
    render_abx_feedback_loop_markdown,
    render_abx_response_template_markdown,
)
from evaluation_harness.compare import recommend_preview_fixed_input_set
from evaluation_harness.models import ExperimentRecord


def build_human_abx_packet(
    records: list[ExperimentRecord] | None = None,
    *,
    expected_input_texts: tuple[str, ...] | None = None,
    expected_seeds: tuple[int, ...] | None = None,
    baseline_generator: str = "baseline-outline",
    question: str = "どちらが人間の手書きに近いか",
    recommendation: dict[str, Any] | None = None,
    focus_areas: tuple[str, ...] | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    if recommendation is None:
        if records is None:
            raise ValueError("records or recommendation is required")
        if expected_input_texts is None:
            raise ValueError("expected_input_texts is required when recommendation is not provided")
        if expected_seeds is None:
            expected_seeds = (1,)
        recommendation = recommend_preview_fixed_input_set(
            records,
            expected_input_texts=expected_input_texts,
            expected_seeds=expected_seeds,
            baseline_generator=baseline_generator,
            include_preview_comparison_details=False,
            include_preview_artifact_details=False,
        )
        baseline_preview_by_group = _baseline_preview_paths_from_records(records, baseline_generator=baseline_generator)
        record_count = len(records)
        packet_baseline_generator = baseline_generator
        packet_expected_input_texts = list(expected_input_texts)
        packet_expected_seeds = list(expected_seeds)
    else:
        baseline_preview_by_group = _baseline_preview_paths_from_recommendation(recommendation)
        record_count = _infer_record_count_from_recommendation(recommendation)
        packet_baseline_generator = recommendation.get("baseline_generator", baseline_generator)
        packet_expected_input_texts = list(recommendation.get("expected_input_texts", []))
        packet_expected_seeds = list(recommendation.get("expected_seeds", []))

    focus_area_filter = {area for area in (focus_areas or ()) if area}
    focus_area_order: list[str] = []
    seen_focus_areas: set[str] = set()
    for area in focus_areas or ():
        if not area or area in seen_focus_areas:
            continue
        focus_area_order.append(area)
        seen_focus_areas.add(area)
    items: list[dict[str, Any]] = []
    for item in recommendation["recommendations"]:
        selected = item["selected_candidate"]
        if selected is None:
            continue
        selected_focus_area = _selected_candidate_focus_area(selected, item)
        if focus_area_filter and selected_focus_area not in focus_area_filter:
            continue
        baseline_preview = baseline_preview_by_group.get((item["input_text"], item["seed"]), "")
        if not baseline_preview:
            continue

        items.append(
            _build_item(
                item_id=f"{item['input_text']}:{item['seed']}",
                prompt=item["input_text"],
                question=question,
                baseline_experiment_id=item["baseline_experiment_id"],
                candidate_experiment_id=selected["experiment_id"],
                candidate_profile_id=selected["profile_id"],
                baseline_preview=baseline_preview,
                candidate_preview=selected["preview"]["path"],
                expected_preference="B",
                selected_failure_tags=list(selected["inferred_failure_tags"]),
                selected_next_actions=list(selected["suggested_next_actions"]),
                focus_area=selected_focus_area,
                selection_status=item["selection_status"],
            )
        )

    items = _order_packet_items_by_focus_area(
        items,
        focus_area_order=focus_area_order,
        max_items=max_items,
    )

    selected_profile_counts = _count_by(items, "candidate_profile_id")
    focus_area_counts = _count_by(items, "focus_area")
    recommended_action_counts = _count_by_nested_lists(items, "selected_next_actions")

    return {
        "record_count": record_count,
        "baseline_generator": packet_baseline_generator,
        "expected_input_texts": packet_expected_input_texts,
        "expected_seeds": packet_expected_seeds,
        "expected_group_count": recommendation["expected_group_count"],
        "selected_candidate_count": len(items),
        "selected_coverage_ratio": recommendation["selected_coverage_ratio"],
        "selected_profile_counts": selected_profile_counts,
        "candidate_profile_counts": recommendation.get("candidate_profile_counts", {}),
        "focus_area_counts": focus_area_counts,
        "recommended_action_counts": recommended_action_counts,
        "abx_items": items,
        "packet_focus_areas": sorted(focus_area_filter),
        "packet_max_items": max_items,
        "source_selected_candidate_count": recommendation["selected_candidate_count"],
    }


def render_human_abx_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Human ABX Packet",
        "",
        f"- record_count: `{packet['record_count']}`",
        f"- expected_group_count: `{packet['expected_group_count']}`",
        f"- selected_candidate_count: `{packet['selected_candidate_count']}`",
        f"- selected_coverage_ratio: `{packet['selected_coverage_ratio']}`",
        f"- selected_profile_counts: `{packet.get('selected_profile_counts', {})}`",
        f"- candidate_profile_counts: `{packet.get('candidate_profile_counts', {})}`",
        f"- focus_area_counts: `{packet['focus_area_counts']}`",
        f"- recommended_action_counts: `{packet['recommended_action_counts']}`",
        f"- packet_focus_areas: `{packet.get('packet_focus_areas', [])}`",
        f"- packet_max_items: `{packet.get('packet_max_items', None)}`",
        f"- source_selected_candidate_count: `{packet.get('source_selected_candidate_count', packet['selected_candidate_count'])}`",
        "",
        "## ABX Items",
        "",
    ]
    if not packet["abx_items"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in packet["abx_items"]:
        lines.extend(
            [
                f"### {item['item_id']}",
                "",
                f"- input_text: `{item['prompt']}`",
                f"- question: `{item['question']}`",
                f"- candidate_profile_id: `{item['candidate_profile_id']}`",
                f"- baseline_experiment_id: `{item['baseline_experiment_id']}`",
                f"- candidate_experiment_id: `{item['candidate_experiment_id']}`",
                f"- expected_preference: `{item['expected_preference']}`",
                f"- selected_failure_tags: `{item['selected_failure_tags']}`",
                f"- selected_next_actions: `{item['selected_next_actions']}`",
                f"- focus_area: `{item['focus_area']}`",
                f"- selection_status: `{item['selection_status']}`",
                f"- option_a_artifact: `{item['option_a_artifact']}`",
                f"- option_b_artifact: `{item['option_b_artifact']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _build_item(
    *,
    item_id: str,
    prompt: str,
    question: str,
    baseline_experiment_id: str,
    candidate_experiment_id: str,
    candidate_profile_id: str,
    baseline_preview: str,
    candidate_preview: str,
    expected_preference: str | None,
    selected_failure_tags: list[str],
    selected_next_actions: list[str],
    focus_area: str,
    selection_status: str,
) -> dict[str, Any]:
    return AbxItem(
        item_id=item_id,
        prompt=prompt,
        option_a_artifact=baseline_preview,
        option_b_artifact=candidate_preview,
        question=question,
        expected_preference=expected_preference,
    ).to_dict() | {
        "baseline_experiment_id": baseline_experiment_id,
        "candidate_experiment_id": candidate_experiment_id,
        "candidate_profile_id": candidate_profile_id,
        "selected_failure_tags": selected_failure_tags,
        "selected_next_actions": selected_next_actions,
        "focus_area": focus_area,
        "selection_status": selection_status,
    }


def _baseline_preview_paths_from_records(
    records: list[ExperimentRecord],
    *,
    baseline_generator: str,
) -> dict[tuple[str, int], str]:
    baseline_preview_by_group: dict[tuple[str, int], str] = {}
    for record in records:
        if record.generator != baseline_generator:
            continue
        preview = record.artifacts.get("preview", "")
        if not preview:
            continue
        baseline_preview_by_group[(record.input_text, record.seed)] = preview
    return baseline_preview_by_group


def _baseline_preview_paths_from_recommendation(
    recommendation: dict[str, Any],
) -> dict[tuple[str, int], str]:
    baseline_preview_by_group: dict[tuple[str, int], str] = {}
    for item in recommendation.get("preview_comparisons", []):
        preview = item.get("baseline_preview", {})
        path = preview.get("path", "")
        if not path:
            continue
        key = (item.get("input_text", ""), item.get("seed", 0))
        baseline_preview_by_group.setdefault(key, path)
    return baseline_preview_by_group


def _infer_record_count_from_recommendation(recommendation: dict[str, Any]) -> int:
    experiment_ids: set[str] = set()
    for item in recommendation.get("preview_comparisons", []):
        baseline_id = item.get("baseline_experiment_id", "")
        candidate_id = item.get("candidate_experiment_id", "")
        if baseline_id:
            experiment_ids.add(baseline_id)
        if candidate_id:
            experiment_ids.add(candidate_id)
    for item in recommendation.get("recommendations", []):
        baseline_id = item.get("baseline_experiment_id", "")
        selected = item.get("selected_candidate") or {}
        candidate_id = selected.get("experiment_id", "")
        if baseline_id:
            experiment_ids.add(baseline_id)
        if candidate_id:
            experiment_ids.add(candidate_id)
    return len(experiment_ids)


def _selected_candidate_focus_area(selected: dict[str, Any], item: dict[str, Any]) -> str:
    focus_area = selected.get("focus_area", "")
    if focus_area:
        return str(focus_area)
    actions_focus_area = _focus_area_from_actions(selected.get("suggested_next_actions", []))
    if actions_focus_area:
        return actions_focus_area
    failure_focus_area = _focus_area_from_tags(list(selected.get("inferred_failure_tags", [])))
    if failure_focus_area:
        return failure_focus_area
    return _focus_area_from_tags(list(item.get("selected_failure_tags", [])))


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "")).strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_by_nested_lists(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        values = item.get(key, [])
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def _order_packet_items_by_focus_area(
    items: list[dict[str, Any]],
    *,
    focus_area_order: list[str],
    max_items: int | None,
) -> list[dict[str, Any]]:
    if max_items is not None and max_items <= 0:
        max_items = None
    if len(focus_area_order) <= 1:
        return items if max_items is None else items[:max_items]

    grouped: dict[str, list[dict[str, Any]]] = {area: [] for area in focus_area_order}
    fallback: list[dict[str, Any]] = []
    for item in items:
        focus_area = str(item.get("focus_area", "")).strip()
        if focus_area in grouped:
            grouped[focus_area].append(item)
        else:
            fallback.append(item)

    ordered: list[dict[str, Any]] = []
    while True:
        progressed = False
        for focus_area in focus_area_order:
            bucket = grouped.get(focus_area, [])
            if not bucket:
                continue
            ordered.append(bucket.pop(0))
            progressed = True
            if max_items is not None and len(ordered) >= max_items:
                return ordered
        if not progressed:
            break

    for item in fallback:
        ordered.append(item)
        if max_items is not None and len(ordered) >= max_items:
            return ordered
    return ordered if max_items is None else ordered[:max_items]


__all__ = [
    "build_abx_response_template",
    "build_human_abx_feedback_loop",
    "build_human_abx_packet",
    "load_abx_responses",
    "render_abx_feedback_loop_markdown",
    "render_abx_response_template_markdown",
    "render_human_abx_packet_markdown",
]

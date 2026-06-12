from __future__ import annotations

from typing import Any

from evaluation_harness.abx import (
    AbxItem,
    build_abx_response_template,
    build_human_abx_feedback_loop,
    load_abx_responses,
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

    items: list[dict[str, Any]] = []
    for item in recommendation["recommendations"]:
        selected = item["selected_candidate"]
        if selected is None:
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
                selection_status=item["selection_status"],
            )
        )

    return {
        "record_count": record_count,
        "baseline_generator": packet_baseline_generator,
        "expected_input_texts": packet_expected_input_texts,
        "expected_seeds": packet_expected_seeds,
        "expected_group_count": recommendation["expected_group_count"],
        "selected_candidate_count": recommendation["selected_candidate_count"],
        "selected_coverage_ratio": recommendation["selected_coverage_ratio"],
        "selected_profile_counts": recommendation.get("selected_profile_counts", {}),
        "candidate_profile_counts": recommendation.get("candidate_profile_counts", {}),
        "focus_area_counts": recommendation["focus_area_counts"],
        "recommended_action_counts": recommendation["recommended_action_counts"],
        "abx_items": items,
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


__all__ = [
    "build_abx_response_template",
    "build_human_abx_feedback_loop",
    "build_human_abx_packet",
    "load_abx_responses",
    "render_abx_feedback_loop_markdown",
    "render_abx_response_template_markdown",
    "render_human_abx_packet_markdown",
]

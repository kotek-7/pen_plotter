from __future__ import annotations

from typing import Any

from evaluation_harness.abx import AbxItem
from evaluation_harness.compare import recommend_preview_fixed_input_set
from evaluation_harness.models import ExperimentRecord


def build_human_abx_packet(
    records: list[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...],
    expected_seeds: tuple[int, ...] = (1,),
    baseline_generator: str = "baseline-outline",
    question: str = "どちらが人間の手書きに近いか",
) -> dict[str, Any]:
    recommendation = recommend_preview_fixed_input_set(
        records,
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
    )

    items: list[dict[str, Any]] = []
    for item in recommendation["recommendations"]:
        selected = item["selected_candidate"]
        if selected is None:
            continue
        baseline_preview = next(
            (
                record.artifacts.get("preview", "")
                for record in records
                if record.experiment_id == item["baseline_experiment_id"]
            ),
            "",
        )
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
        "record_count": len(records),
        "baseline_generator": baseline_generator,
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
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

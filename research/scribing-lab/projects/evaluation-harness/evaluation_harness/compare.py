from __future__ import annotations

from collections import Counter
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import infer_offline_failure_tags, suggested_next_actions
from evaluation_harness.preview_metrics import (
    compare_preview_artifacts,
    summarize_preview_artifact,
)


DEFAULT_COMPARE_METRICS: tuple[str, ...] = (
    "stroke_count",
    "draw_distance_mm",
    "penup_distance_mm",
    "duration_ms",
    "velocity_peak_count",
    "draw_speed_cv",
    "stroke_start_spacing_cv",
    "baseline_drift_mm",
    "repeated_char_ratio",
)


def compare_against_baseline(
    records: Iterable[ExperimentRecord],
    *,
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    grouped: dict[tuple[str, int], list[ExperimentRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.input_text, record.seed)].append(record)

    comparisons: list[dict[str, Any]] = []
    missing_baseline: list[dict[str, Any]] = []
    for (input_text, seed), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        baseline = next((record for record in group if record.generator == baseline_generator), None)
        if baseline is None:
            missing_baseline.append({"input_text": input_text, "seed": seed})
            continue
        for candidate in group:
            if candidate.experiment_id == baseline.experiment_id:
                continue
            comparisons.append(
                {
                    "input_text": input_text,
                    "seed": seed,
                    "baseline_experiment_id": baseline.experiment_id,
                    "candidate_experiment_id": candidate.experiment_id,
                    "candidate_generator": candidate.generator,
                    "metric_deltas": _metric_deltas(baseline, candidate, metrics),
                    "baseline_failure_tags": list(baseline.failure_tags),
                    "candidate_failure_tags": list(candidate.failure_tags),
                    "resolved_failure_tags": sorted(
                        set(baseline.failure_tags) - set(candidate.failure_tags)
                    ),
                    "new_failure_tags": sorted(set(candidate.failure_tags) - set(baseline.failure_tags)),
                }
            )

    return {
        "baseline_generator": baseline_generator,
        "metric_names": list(metrics),
        "comparison_count": len(comparisons),
        "missing_baseline": missing_baseline,
        "comparisons": comparisons,
    }


def compare_fixed_input_set(
    records: Iterable[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    record_list = list(records)
    baseline_comparison = compare_against_baseline(
        record_list,
        baseline_generator=baseline_generator,
        metrics=metrics,
    )
    grouped = _group_records_by_input_and_seed(record_list)
    expected_groups = [(input_text, seed) for input_text in expected_input_texts for seed in expected_seeds]

    group_summaries: list[dict[str, Any]] = []
    complete_group_count = 0
    for input_text, seed in expected_groups:
        group = grouped.get((input_text, seed), [])
        baseline = next((record for record in group if record.generator == baseline_generator), None)
        candidate_count = sum(1 for record in group if record.generator != baseline_generator)
        status: str
        if baseline is None:
            status = "missing-baseline"
        elif candidate_count == 0:
            status = "baseline-only"
        else:
            status = "complete"
            complete_group_count += 1

        group_summaries.append(
            {
                "input_text": input_text,
                "seed": seed,
                "status": status,
                "record_count": len(group),
                "candidate_count": candidate_count,
                "has_baseline": baseline is not None,
            }
        )

    expected_group_count = len(expected_groups)
    return {
        **baseline_comparison,
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
        "expected_group_count": expected_group_count,
        "complete_group_count": complete_group_count,
        "coverage_ratio": round(complete_group_count / expected_group_count, 4)
        if expected_group_count
        else 0.0,
        "group_summaries": group_summaries,
    }


def compare_preview_fixed_input_set(
    records: Iterable[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    record_list = list(records)
    baseline_comparison = compare_against_baseline(
        record_list,
        baseline_generator=baseline_generator,
        metrics=metrics,
    )
    grouped = _group_records_by_input_and_seed(record_list)
    expected_groups = [(input_text, seed) for input_text in expected_input_texts for seed in expected_seeds]

    preview_comparisons: list[dict[str, Any]] = []
    preview_group_summaries: list[dict[str, Any]] = []
    preview_ready_count = 0
    preview_hash_changed_count = 0

    for input_text, seed in expected_groups:
        group = grouped.get((input_text, seed), [])
        baseline = next((record for record in group if record.generator == baseline_generator), None)
        candidate_records = [record for record in group if record.generator != baseline_generator]
        if baseline is None:
            preview_group_summaries.append(
                {
                    "input_text": input_text,
                    "seed": seed,
                    "status": "missing-baseline",
                    "record_count": len(group),
                    "candidate_count": len(candidate_records),
                    "has_preview_baseline": False,
                    "preview_comparison_count": 0,
                }
            )
            continue

        group_comparison_count = 0
        baseline_preview = _preview_artifact_summary(baseline.artifacts.get("preview", ""))
        for candidate in candidate_records:
            candidate_preview = _preview_artifact_summary(candidate.artifacts.get("preview", ""))
            preview_item = {
                "input_text": input_text,
                "seed": seed,
                "baseline_experiment_id": baseline.experiment_id,
                "candidate_experiment_id": candidate.experiment_id,
                "candidate_generator": candidate.generator,
                "baseline_preview": baseline_preview,
                "candidate_preview": candidate_preview,
                "preview_comparable": baseline_preview is not None and candidate_preview is not None,
                "preview_hash_changed": None,
                "preview_size_delta": None,
                "preview_similarity": None,
            }
            if preview_item["preview_comparable"]:
                group_comparison_count += 1
                preview_ready_count += 1
                preview_item["preview_hash_changed"] = (
                    baseline_preview["sha256"] != candidate_preview["sha256"]
                )
                preview_item["preview_size_delta"] = (
                    candidate_preview["size_bytes"] - baseline_preview["size_bytes"]
                )
                preview_item["preview_similarity"] = compare_preview_artifacts(
                    baseline_preview,
                    candidate_preview,
                )
                if preview_item["preview_hash_changed"]:
                    preview_hash_changed_count += 1
            preview_comparisons.append(preview_item)

        status = "baseline-only" if not candidate_records else "complete"
        preview_group_summaries.append(
            {
                "input_text": input_text,
                "seed": seed,
                "status": status,
                "record_count": len(group),
                "candidate_count": len(candidate_records),
                "has_preview_baseline": baseline_preview is not None,
                "preview_comparison_count": group_comparison_count,
            }
        )

    expected_group_count = len(expected_groups)
    return {
        **baseline_comparison,
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
        "expected_group_count": expected_group_count,
        "preview_ready_count": preview_ready_count,
        "preview_hash_changed_count": preview_hash_changed_count,
        "preview_group_summaries": preview_group_summaries,
        "preview_comparisons": preview_comparisons,
        "preview_coverage_ratio": round(preview_ready_count / expected_group_count, 4)
        if expected_group_count
        else 0.0,
    }


def recommend_preview_fixed_input_set(
    records: Iterable[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    comparison = compare_preview_fixed_input_set(
        records,
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
        metrics=metrics,
    )
    record_list = list(records)
    grouped = _group_records_by_input_and_seed(record_list)
    expected_groups = [
        (input_text, seed) for input_text in expected_input_texts for seed in expected_seeds
    ]

    recommendations: list[dict[str, Any]] = []
    selected_candidate_count = 0
    recommended_action_counts: Counter[str] = Counter()
    focus_area_counts: Counter[str] = Counter()

    for input_text, seed in expected_groups:
        group = grouped.get((input_text, seed), [])
        baseline = next((record for record in group if record.generator == baseline_generator), None)
        candidate_records = [record for record in group if record.generator != baseline_generator]
        baseline_preview = _preview_artifact_summary(baseline.artifacts.get("preview", "")) if baseline else None
        candidate_items: list[dict[str, Any]] = []
        for candidate in candidate_records:
            preview_summary = _preview_artifact_summary(candidate.artifacts.get("preview", ""))
            inferred_tags = infer_offline_failure_tags(candidate)
            candidate_actions = suggested_next_actions(inferred_tags)
            preview_hash_changed = (
                None
                if baseline_preview is None or preview_summary is None
                else baseline_preview["sha256"] != preview_summary["sha256"]
            )
            candidate_items.append(
                {
                    "experiment_id": candidate.experiment_id,
                    "profile_id": candidate.profile_id,
                    "generator": candidate.generator,
                    "preview": preview_summary,
                    "preview_comparable": baseline_preview is not None and preview_summary is not None,
                    "preview_hash_changed": preview_hash_changed,
                    "inferred_failure_tags": inferred_tags,
                    "suggested_next_actions": candidate_actions,
                    "selection_key": _preview_candidate_selection_key(
                        preview_summary=preview_summary,
                        inferred_failure_tags=inferred_tags,
                        preview_hash_changed=bool(preview_hash_changed),
                        experiment_id=candidate.experiment_id,
                    ),
                }
            )

        selected = None
        comparable_candidates = [item for item in candidate_items if item["preview_comparable"]]
        if comparable_candidates:
            selected = min(comparable_candidates, key=lambda item: item["selection_key"])
            selected_candidate_count += 1
            if selected["suggested_next_actions"]:
                for action in selected["suggested_next_actions"]:
                    recommended_action_counts[action] += 1
            else:
                recommended_action_counts["preview を基準に次の profile 比較を行う"] += 1
            focus_area_counts[_focus_area_from_tags(selected["inferred_failure_tags"])] += 1

        recommendations.append(
            {
                "input_text": input_text,
                "seed": seed,
                "baseline_experiment_id": baseline.experiment_id if baseline else "",
                "selected_candidate": selected,
                "candidate_count": len(candidate_records),
                "preview_candidate_count": len(comparable_candidates),
                "selection_status": "selected" if selected else "no-preview-candidate",
                "candidate_items": candidate_items,
            }
        )

    expected_group_count = comparison["expected_group_count"]
    return {
        **comparison,
        "selected_candidate_count": selected_candidate_count,
        "selected_coverage_ratio": round(selected_candidate_count / expected_group_count, 4)
        if expected_group_count
        else 0.0,
        "recommended_action_counts": dict(sorted(recommended_action_counts.items())),
        "focus_area_counts": dict(sorted(focus_area_counts.items())),
        "recommendations": recommendations,
    }


def propose_preview_fixed_input_set(
    records: Iterable[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    recommendation = recommend_preview_fixed_input_set(
        records,
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
        metrics=metrics,
    )

    revision_plans: list[dict[str, Any]] = []
    revision_area_counts: Counter[str] = Counter()
    for item in recommendation["recommendations"]:
        selected = item["selected_candidate"]
        if selected is None:
            revision_plans.append(
                {
                    "input_text": item["input_text"],
                    "seed": item["seed"],
                    "status": "no-preview-candidate",
                    "focus_area": "preview",
                    "candidate_experiment_id": "",
                    "proposed_changes": [],
                    "next_experiment_hint": "preview artifact を持つ候補を追加して比較する",
                }
            )
            continue

        focus_area = _focus_area_from_tags(selected["inferred_failure_tags"])
        proposed_changes = _proposed_changes_for_tags(selected["inferred_failure_tags"], focus_area)
        revision_area_counts[focus_area] += 1
        revision_plans.append(
            {
                "input_text": item["input_text"],
                "seed": item["seed"],
                "status": "selected",
                "baseline_experiment_id": item["baseline_experiment_id"],
                "candidate_experiment_id": selected["experiment_id"],
                "candidate_profile_id": selected["profile_id"],
                "focus_area": focus_area,
                "selected_failure_tags": list(selected["inferred_failure_tags"]),
                "selected_next_actions": list(selected["suggested_next_actions"]),
                "proposed_changes": proposed_changes,
                "next_experiment_hint": _next_experiment_hint(focus_area, selected["inferred_failure_tags"]),
            }
        )

    return {
        **recommendation,
        "revision_area_counts": dict(sorted(revision_area_counts.items())),
        "revision_plans": revision_plans,
    }


def preview_iteration_fixed_input_set(
    records: Iterable[ExperimentRecord],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    baseline_generator: str = "baseline-outline",
    metrics: tuple[str, ...] = DEFAULT_COMPARE_METRICS,
) -> dict[str, Any]:
    proposal = propose_preview_fixed_input_set(
        records,
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
        metrics=metrics,
    )
    selected_candidate_count = proposal["selected_candidate_count"]
    expected_group_count = proposal["expected_group_count"]
    if selected_candidate_count == 0:
        iteration_status = "needs-more-preview-data"
    elif selected_candidate_count < expected_group_count:
        iteration_status = "partial"
    else:
        iteration_status = "ready"

    next_experiment_hints = sorted(
        {
            plan["next_experiment_hint"]
            for plan in proposal["revision_plans"]
            if plan.get("status") == "selected"
        }
    )
    if not next_experiment_hints:
        next_experiment_hints = ["preview artifact を持つ候補を追加して比較する"]

    return {
        **proposal,
        "iteration_status": iteration_status,
        "iteration_next_experiment_hints": next_experiment_hints,
        "iteration_selected_area_count": len(proposal["revision_area_counts"]),
    }


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Baseline Comparison Report",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- comparison_count: `{comparison['comparison_count']}`",
        f"- metric_names: `{comparison['metric_names']}`",
        "",
    ]
    if comparison["missing_baseline"]:
        lines.extend(["## Missing Baseline", ""])
        for item in comparison["missing_baseline"]:
            lines.append(f"- input=`{item['input_text']}`, seed=`{item['seed']}`")
        lines.append("")

    lines.extend(["## Comparisons", ""])
    if not comparison["comparisons"]:
        lines.append("- none")
    for item in comparison["comparisons"]:
        lines.extend(
            [
                f"### {item['candidate_experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- baseline: `{item['baseline_experiment_id']}`",
                f"- candidate_generator: `{item['candidate_generator']}`",
                f"- resolved_failure_tags: `{item['resolved_failure_tags']}`",
                f"- new_failure_tags: `{item['new_failure_tags']}`",
                "- metric_deltas:",
            ]
        )
        for name, delta in item["metric_deltas"].items():
            lines.append(f"  - {name}: `{delta}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_fixed_input_comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Fixed Input Comparison Report",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- expected_input_texts: `{comparison['expected_input_texts']}`",
        f"- expected_seeds: `{comparison['expected_seeds']}`",
        f"- expected_group_count: `{comparison['expected_group_count']}`",
        f"- complete_group_count: `{comparison['complete_group_count']}`",
        f"- coverage_ratio: `{comparison['coverage_ratio']}`",
        "",
        "## Coverage",
        "",
    ]
    for item in comparison["group_summaries"]:
        lines.append(
            "- "
            f"input=`{item['input_text']}`, "
            f"seed=`{item['seed']}`, "
            f"status=`{item['status']}`, "
            f"record_count=`{item['record_count']}`, "
            f"candidate_count=`{item['candidate_count']}`"
        )
    lines.extend(["", "## Comparisons", ""])
    if not comparison["comparisons"]:
        lines.append("- none")
    for item in comparison["comparisons"]:
        lines.extend(
            [
                f"### {item['candidate_experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- baseline: `{item['baseline_experiment_id']}`",
                f"- candidate_generator: `{item['candidate_generator']}`",
                f"- resolved_failure_tags: `{item['resolved_failure_tags']}`",
                f"- new_failure_tags: `{item['new_failure_tags']}`",
                "- metric_deltas:",
            ]
        )
        for name, delta in item["metric_deltas"].items():
            lines.append(f"  - {name}: `{delta}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_preview_fixed_input_comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Preview Comparison Report",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- expected_input_texts: `{comparison['expected_input_texts']}`",
        f"- expected_seeds: `{comparison['expected_seeds']}`",
        f"- expected_group_count: `{comparison['expected_group_count']}`",
        f"- preview_ready_count: `{comparison['preview_ready_count']}`",
        f"- preview_hash_changed_count: `{comparison['preview_hash_changed_count']}`",
        f"- preview_coverage_ratio: `{comparison['preview_coverage_ratio']}`",
        "",
        "## Preview Coverage",
        "",
    ]
    for item in comparison["preview_group_summaries"]:
        lines.append(
            "- "
            f"input=`{item['input_text']}`, "
            f"seed=`{item['seed']}`, "
            f"status=`{item['status']}`, "
            f"record_count=`{item['record_count']}`, "
            f"candidate_count=`{item['candidate_count']}`, "
            f"preview_comparison_count=`{item['preview_comparison_count']}`"
        )
    lines.extend(["", "## Preview Deltas", ""])
    if not comparison["preview_comparisons"]:
        lines.append("- none")
    for item in comparison["preview_comparisons"]:
        lines.extend(
            [
                f"### {item['candidate_experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- baseline: `{item['baseline_experiment_id']}`",
                f"- candidate_generator: `{item['candidate_generator']}`",
                f"- preview_comparable: `{item['preview_comparable']}`",
                f"- preview_hash_changed: `{item['preview_hash_changed']}`",
                f"- preview_size_delta: `{item['preview_size_delta']}`",
                f"- preview_similarity: `{item['preview_similarity']}`",
                f"- baseline_preview: `{item['baseline_preview']}`",
                f"- candidate_preview: `{item['candidate_preview']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_preview_recommendation_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Preview Recommendation Report",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- expected_group_count: `{comparison['expected_group_count']}`",
        f"- selected_candidate_count: `{comparison['selected_candidate_count']}`",
        f"- selected_coverage_ratio: `{comparison['selected_coverage_ratio']}`",
        f"- focus_area_counts: `{comparison['focus_area_counts']}`",
        f"- recommended_action_counts: `{comparison['recommended_action_counts']}`",
        "",
        "## Recommendations",
        "",
    ]
    if not comparison["recommendations"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in comparison["recommendations"]:
        lines.extend(
            [
                f"### input={item['input_text']} seed={item['seed']}",
                "",
                f"- baseline_experiment_id: `{item['baseline_experiment_id']}`",
                f"- selection_status: `{item['selection_status']}`",
                f"- candidate_count: `{item['candidate_count']}`",
                f"- preview_candidate_count: `{item['preview_candidate_count']}`",
            ]
        )
        selected = item["selected_candidate"]
        if selected is None:
            lines.append("- selected_candidate: `none`")
        else:
            lines.extend(
                [
                    f"- selected_candidate: `{selected['experiment_id']}`",
                    f"- selected_profile_id: `{selected['profile_id']}`",
                    f"- selected_preview_hash_changed: `{selected['preview_hash_changed']}`",
                    f"- selected_failure_tags: `{selected['inferred_failure_tags']}`",
                    f"- selected_next_actions: `{selected['suggested_next_actions']}`",
                    f"- focus_area: `{_focus_area_from_tags(selected['inferred_failure_tags'])}`",
                ]
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_preview_revision_plan_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Preview Revision Plan",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- expected_group_count: `{comparison['expected_group_count']}`",
        f"- selected_candidate_count: `{comparison['selected_candidate_count']}`",
        f"- selected_coverage_ratio: `{comparison['selected_coverage_ratio']}`",
        f"- revision_area_counts: `{comparison['revision_area_counts']}`",
        "",
        "## Revision Plans",
        "",
    ]
    if not comparison["revision_plans"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in comparison["revision_plans"]:
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


def render_preview_iteration_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Preview Iteration Report",
        "",
        f"- baseline_generator: `{comparison['baseline_generator']}`",
        f"- expected_group_count: `{comparison['expected_group_count']}`",
        f"- preview_ready_count: `{comparison['preview_ready_count']}`",
        f"- selected_candidate_count: `{comparison['selected_candidate_count']}`",
        f"- selected_coverage_ratio: `{comparison['selected_coverage_ratio']}`",
        f"- iteration_status: `{comparison['iteration_status']}`",
        f"- iteration_selected_area_count: `{comparison['iteration_selected_area_count']}`",
        f"- iteration_next_experiment_hints: `{comparison['iteration_next_experiment_hints']}`",
        "",
        "## Iteration Summary",
        "",
        f"- focus_area_counts: `{comparison['focus_area_counts']}`",
        f"- recommended_action_counts: `{comparison['recommended_action_counts']}`",
        f"- revision_area_counts: `{comparison['revision_area_counts']}`",
        "",
        "## Revision Plans",
        "",
    ]
    if not comparison["revision_plans"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in comparison["revision_plans"]:
        lines.extend(
            [
                f"### input={item['input_text']} seed={item['seed']}",
                "",
                f"- status: `{item['status']}`",
                f"- focus_area: `{item['focus_area']}`",
                f"- candidate_experiment_id: `{item['candidate_experiment_id']}`",
                f"- candidate_profile_id: `{item.get('candidate_profile_id', '')}`",
                f"- next_experiment_hint: `{item['next_experiment_hint']}`",
            ]
        )
        if item["proposed_changes"]:
            lines.append("- proposed_changes:")
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
            lines.append("- proposed_changes: `none`")
        lines.append("")
    return "\n".join(lines) + "\n"


def _metric_deltas(
    baseline: ExperimentRecord,
    candidate: ExperimentRecord,
    metric_names: tuple[str, ...],
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for name in metric_names:
        if name not in baseline.metrics or name not in candidate.metrics:
            continue
        base_value = baseline.metrics[name]
        candidate_value = candidate.metrics[name]
        if isinstance(base_value, (int, float)) and isinstance(candidate_value, (int, float)):
            deltas[name] = round(float(candidate_value) - float(base_value), 4)
    return deltas


def _group_records_by_input_and_seed(
    records: Iterable[ExperimentRecord],
) -> dict[tuple[str, int], list[ExperimentRecord]]:
    grouped: dict[tuple[str, int], list[ExperimentRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.input_text, record.seed)].append(record)
    return grouped


def _preview_artifact_summary(path_text: str) -> dict[str, Any] | None:
    return summarize_preview_artifact(path_text)


def _preview_candidate_selection_key(
    *,
    preview_summary: dict[str, Any] | None,
    inferred_failure_tags: list[str],
    preview_hash_changed: bool,
    experiment_id: str,
) -> tuple[int, int, int, str]:
    return (
        0 if preview_summary is not None else 1,
        len(inferred_failure_tags),
        0 if preview_hash_changed else 1,
        experiment_id,
    )


def _focus_area_from_tags(tags: list[str]) -> str:
    priority = (
        ("plotter-unsafe", "safety"),
        ("too-font-like", "dictionary"),
        ("skeleton-too-rigid", "dictionary"),
        ("too-uniform", "motion"),
        ("over-jittered", "motion"),
        ("line-too-mechanical", "layout"),
        ("spacing-unnatural", "layout"),
        ("terminal-too-uniform", "terminal"),
        ("repeated-char-too-identical", "dictionary"),
    )
    tag_set = set(tags)
    for tag, area in priority:
        if tag in tag_set:
            return area
    return "preview"


def _proposed_changes_for_tags(tags: list[str], focus_area: str) -> list[dict[str, Any]]:
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
    proposed: list[dict[str, Any]] = []
    for tag in tags:
        proposed.extend(change_map.get(tag, []))

    if not proposed:
        proposed.append(
            {
                "target": focus_area,
                "parameter": "profile_id",
                "direction": "keep-compare",
                "amount_hint": None,
                "reason": "明確な failure tag がないため、同条件で別 profile を比較する",
            }
        )
    return proposed


def _next_experiment_hint(focus_area: str, tags: list[str]) -> str:
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

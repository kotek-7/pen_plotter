from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation_harness.compare import preview_iteration_fixed_input_set
from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.structure_motion import run_structure_motion
from evaluation_harness.structure_uniform import DEFAULT_STRUCTURE_INPUTS
from evaluation_harness.writer_profile import build_revision_profile, resolve_writer_profile
from writer_profile import estimate_writer_profile_from_jsonl


def run_preview_revision_loop_fixed_input_set(
    root: Path,
    *,
    expected_input_texts: tuple[str, ...],
    expected_seeds: tuple[int, ...],
    baseline_generator: str = "baseline-outline",
) -> dict[str, Any]:
    registry = ExperimentRegistry(root / "registry.jsonl")
    before_records = registry.load_all()
    before_iteration = preview_iteration_fixed_input_set(
        before_records,
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
    )

    applications: list[dict[str, Any]] = []
    rerun_records = []
    before_by_id = {record.experiment_id: record for record in before_records}
    for plan in before_iteration["revision_plans"]:
        if plan["status"] != "selected":
            applications.append(
                {
                    "input_text": plan["input_text"],
                    "seed": plan["seed"],
                    "status": plan["status"],
                    "candidate_experiment_id": plan.get("candidate_experiment_id", ""),
                    "revision_experiment_id": "",
                    "revision_profile_id": "",
                    "applied_changes": [],
                    "unapplied_changes": [],
                }
            )
            continue

        candidate_profile = resolve_writer_profile(plan["candidate_profile_id"])
        revision_profile_id = _revision_profile_id(plan)
        application = build_revision_profile(
            candidate_profile,
            list(plan["proposed_changes"]),
            revision_profile_id=revision_profile_id,
            created_from_experiment=plan["candidate_experiment_id"],
        )
        if not application["applied_changes"]:
            applications.append(
                {
                    "input_text": plan["input_text"],
                    "seed": plan["seed"],
                    "status": "no-applicable-changes",
                    "candidate_experiment_id": plan["candidate_experiment_id"],
                    "revision_experiment_id": "",
                    "revision_profile_id": application["profile"].profile_id,
                    "applied_changes": [],
                    "unapplied_changes": list(application["unapplied_changes"]),
                }
            )
            continue

        experiment_id = _revision_experiment_id(plan, application["profile"].profile_id, registry)
        record = run_structure_motion(
            root=root,
            experiment_id=experiment_id,
            input_text=plan["input_text"],
            seed=plan["seed"],
            writer_profile=application["profile"],
        )
        rerun_records.append(record)
        candidate_record = before_by_id.get(plan["candidate_experiment_id"])
        applications.append(
            {
                "input_text": plan["input_text"],
                "seed": plan["seed"],
                "status": "rerun",
                "candidate_experiment_id": plan["candidate_experiment_id"],
                "revision_experiment_id": record.experiment_id,
                "revision_profile_id": record.profile_id,
                "report": record.artifacts.get("report", ""),
                "preview": record.artifacts.get("preview", ""),
                "applied_changes": list(application["applied_changes"]),
                "unapplied_changes": list(application["unapplied_changes"]),
                "comparison": _compare_revision_outcome(candidate_record, record)
                if candidate_record is not None
                else None,
            }
        )

    after_iteration = preview_iteration_fixed_input_set(
        registry.load_all(),
        expected_input_texts=expected_input_texts,
        expected_seeds=expected_seeds,
        baseline_generator=baseline_generator,
    )
    return {
        "baseline_generator": baseline_generator,
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
        "before_iteration": before_iteration,
        "applications": applications,
        "rerun_count": len(rerun_records),
        "design_principles": _extract_design_principles(applications),
        "comparison_summary": _summarize_comparisons(applications),
        "selected_candidate_delta": (
            after_iteration["selected_candidate_count"] - before_iteration["selected_candidate_count"]
        ),
        "coverage_delta": round(
            after_iteration["selected_coverage_ratio"] - before_iteration["selected_coverage_ratio"],
            4,
        ),
        "after_iteration": after_iteration,
    }


def summarize_preview_revision_loops(packets: list[dict[str, Any]]) -> dict[str, Any]:
    packet_count = len(packets)
    principle_counts: dict[str, int] = {}
    resolved_tag_counts: dict[str, int] = {}
    new_tag_counts: dict[str, int] = {}
    metric_name_counts: dict[str, int] = {}
    before_status_counts: dict[str, int] = {}
    after_status_counts: dict[str, int] = {}
    rerun_counts: list[int] = []
    coverage_deltas: list[float] = []
    selected_candidate_deltas: list[int] = []

    for packet in packets:
        rerun_counts.append(int(packet.get("rerun_count", 0)))
        coverage_deltas.append(float(packet.get("coverage_delta", 0.0)))
        selected_candidate_deltas.append(int(packet.get("selected_candidate_delta", 0)))
        _bump_counts(principle_counts, packet.get("design_principles", []))
        _bump_counts(before_status_counts, [packet.get("before_iteration", {}).get("iteration_status", "")])
        _bump_counts(after_status_counts, [packet.get("after_iteration", {}).get("iteration_status", "")])

        summary = packet.get("comparison_summary", {})
        _bump_counts(resolved_tag_counts, summary.get("resolved_failure_tags", []))
        _bump_counts(new_tag_counts, summary.get("new_failure_tags", []))
        for name in summary.get("metric_names", []):
            metric_name_counts[name] = metric_name_counts.get(name, 0) + 1

    stable_design_principles = sorted(
        principle for principle, count in principle_counts.items() if packet_count and count == packet_count
    )
    recurring_design_principles = sorted(
        principle for principle, count in principle_counts.items() if count >= 2
    )

    return {
        "packet_count": packet_count,
        "rerun_count_total": sum(rerun_counts),
        "rerun_count_mean": round(sum(rerun_counts) / packet_count, 4) if packet_count else 0.0,
        "coverage_delta_mean": round(sum(coverage_deltas) / packet_count, 4) if packet_count else 0.0,
        "selected_candidate_delta_mean": round(
            sum(selected_candidate_deltas) / packet_count, 4
        ) if packet_count else 0.0,
        "design_principle_counts": dict(sorted(principle_counts.items())),
        "stable_design_principles": stable_design_principles,
        "recurring_design_principles": recurring_design_principles,
        "resolved_failure_tag_counts": dict(sorted(resolved_tag_counts.items())),
        "new_failure_tag_counts": dict(sorted(new_tag_counts.items())),
        "comparison_metric_names": sorted(metric_name_counts),
        "comparison_metric_name_counts": dict(sorted(metric_name_counts.items())),
        "before_iteration_status_counts": dict(sorted(before_status_counts.items())),
        "after_iteration_status_counts": dict(sorted(after_status_counts.items())),
        "packets": [
            {
                "baseline_generator": packet.get("baseline_generator", ""),
                "expected_input_texts": list(packet.get("expected_input_texts", [])),
                "expected_seeds": list(packet.get("expected_seeds", [])),
                "rerun_count": packet.get("rerun_count", 0),
                "coverage_delta": packet.get("coverage_delta", 0.0),
                "selected_candidate_delta": packet.get("selected_candidate_delta", 0),
                "design_principles": list(packet.get("design_principles", [])),
                "comparison_summary": packet.get("comparison_summary", {}),
            }
            for packet in packets
        ],
    }


def render_preview_revision_loop_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Preview Revision Loop Summary",
        "",
        f"- packet_count: `{summary['packet_count']}`",
        f"- rerun_count_total: `{summary['rerun_count_total']}`",
        f"- rerun_count_mean: `{summary['rerun_count_mean']}`",
        f"- coverage_delta_mean: `{summary['coverage_delta_mean']}`",
        f"- selected_candidate_delta_mean: `{summary['selected_candidate_delta_mean']}`",
        f"- stable_design_principles: `{summary['stable_design_principles']}`",
        f"- recurring_design_principles: `{summary['recurring_design_principles']}`",
        "",
        "## Design Principles",
        "",
    ]
    if not summary["design_principle_counts"]:
        lines.append("- none")
    else:
        for principle, count in summary["design_principle_counts"].items():
            lines.append(f"- `{principle}`: `{count}`")

    lines.extend(["", "## Comparison Metrics", ""])
    if not summary["comparison_metric_name_counts"]:
        lines.append("- none")
    else:
        for name, count in summary["comparison_metric_name_counts"].items():
            lines.append(f"- `{name}`: `{count}`")

    lines.extend(["", "## Failure Tags", ""])
    if not summary["resolved_failure_tag_counts"] and not summary["new_failure_tag_counts"]:
        lines.append("- none")
    else:
        if summary["resolved_failure_tag_counts"]:
            lines.append("### Resolved")
            for tag, count in summary["resolved_failure_tag_counts"].items():
                lines.append(f"- `{tag}`: `{count}`")
        if summary["new_failure_tag_counts"]:
            lines.append("### New")
            for tag, count in summary["new_failure_tag_counts"].items():
                lines.append(f"- `{tag}`: `{count}`")

    lines.extend(["", "## Packets", ""])
    if not summary["packets"]:
        lines.append("- none")
    else:
        for packet in summary["packets"]:
            lines.extend(
                [
                    f"### {packet['baseline_generator']}",
                    "",
                    f"- expected_input_texts: `{packet['expected_input_texts']}`",
                    f"- expected_seeds: `{packet['expected_seeds']}`",
                    f"- rerun_count: `{packet['rerun_count']}`",
                    f"- coverage_delta: `{packet['coverage_delta']}`",
                    f"- selected_candidate_delta: `{packet['selected_candidate_delta']}`",
                    f"- design_principles: `{packet['design_principles']}`",
                    f"- comparison_summary: `{packet['comparison_summary']}`",
                    "",
                ]
            )
    return "\n".join(lines) + "\n"


def propose_stable_writer_profile_candidates(
    summary: dict[str, Any],
    *,
    base_profile_id: str = "baseline-neat",
) -> dict[str, Any]:
    base_profile = resolve_writer_profile(base_profile_id)
    candidates: list[dict[str, Any]] = []
    for candidate_type, principle_names, min_count in (
        ("stable", summary.get("stable_design_principles", []), int(summary.get("packet_count", 0))),
        ("recurring", summary.get("recurring_design_principles", []), 2),
    ):
        candidate = _build_stable_writer_profile_candidate(
            base_profile,
            candidate_type=candidate_type,
            principles=list(principle_names),
            support_counts=summary.get("design_principle_counts", {}),
            packet_count=int(summary.get("packet_count", 0)),
            min_count=min_count,
        )
        if candidate is not None:
            candidates.append(candidate)

    return {
        "base_profile_id": base_profile_id,
        "packet_count": int(summary.get("packet_count", 0)),
        "stable_design_principles": list(summary.get("stable_design_principles", [])),
        "recurring_design_principles": list(summary.get("recurring_design_principles", [])),
        "candidates": candidates,
    }


def render_stable_writer_profile_candidates_markdown(bundle: dict[str, Any]) -> str:
    lines = [
        "# Stable Writer Profile Candidates",
        "",
        f"- base_profile_id: `{bundle['base_profile_id']}`",
        f"- packet_count: `{bundle['packet_count']}`",
        f"- stable_design_principles: `{bundle['stable_design_principles']}`",
        f"- recurring_design_principles: `{bundle['recurring_design_principles']}`",
        "",
        "## Candidates",
        "",
    ]
    if not bundle["candidates"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in bundle["candidates"]:
        profile = item["profile"]
        lines.extend(
            [
                f"### {item['candidate_type']}",
                "",
                f"- profile_id: `{profile['profile_id']}`",
                f"- parent_profile: `{profile['parent_profile']}`",
                f"- version: `{profile['version']}`",
                f"- support_count: `{item['support_count']}`",
                f"- support_ratio: `{item['support_ratio']}`",
                f"- principles: `{item['principles']}`",
                f"- applied_changes: `{item['applied_changes']}`",
                f"- unapplied_changes: `{item['unapplied_changes']}`",
                f"- notes: `{profile['notes']}`",
                f"- params: `{profile['params']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def evaluate_stable_writer_profile_candidates(
    root: Path,
    summary: dict[str, Any],
    *,
    expected_input_texts: tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    base_profile_id: str = "baseline-neat",
) -> dict[str, Any]:
    bundle = propose_stable_writer_profile_candidates(
        summary,
        base_profile_id=base_profile_id,
    )
    registry = ExperimentRegistry(root / "registry.jsonl")
    base_profile = resolve_writer_profile(base_profile_id)
    baseline_records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(expected_input_texts, start=1):
        for seed in expected_seeds:
            baseline_records.append(
                _run_or_load_structure_motion(
                    root=root,
                    registry=registry,
                    experiment_id=_stable_profile_experiment_id(
                        "baseline",
                        base_profile.profile_id,
                        input_index,
                        seed,
                    ),
                    input_text=input_text,
                    seed=seed,
                    writer_profile=base_profile,
                )
            )

    baseline_by_key = _records_by_input_and_seed(baseline_records)
    candidate_evaluations: list[dict[str, Any]] = []
    selected_profile_ids: list[str] = []

    for candidate in bundle["candidates"]:
        profile = _profile_from_dict(candidate["profile"])
        records: list[ExperimentRecord] = []
        for input_index, input_text in enumerate(expected_input_texts, start=1):
            for seed in expected_seeds:
                records.append(
                    _run_or_load_structure_motion(
                        root=root,
                        registry=registry,
                        experiment_id=_stable_profile_experiment_id(
                            candidate["candidate_type"],
                            profile.profile_id,
                            input_index,
                            seed,
                        ),
                        input_text=input_text,
                        seed=seed,
                        writer_profile=profile,
                    )
                )

        comparison = _compare_against_profile_baseline(records, baseline_by_key)
        selected, selection_reason = _is_selected_stable_candidate(candidate, comparison)
        if selected:
            selected_profile_ids.append(profile.profile_id)
        candidate_evaluations.append(
            {
                **candidate,
                "profile": profile.to_dict(),
                "evaluation": comparison,
                "selected": selected,
                "selection_reason": selection_reason,
            }
        )

    selected_candidates = [item for item in candidate_evaluations if item["selected"]]
    return {
        "base_profile_id": base_profile_id,
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
        "candidate_bundle": bundle,
        "baseline_record_count": len(baseline_records),
        "candidate_count": len(candidate_evaluations),
        "selected_profile_ids": selected_profile_ids,
        "selected_profile_count": len(selected_profile_ids),
        "candidate_evaluations": candidate_evaluations,
        "selected_candidates": selected_candidates,
        "selection_summary": {
            "candidate_count": len(candidate_evaluations),
            "selected_candidate_count": len(selected_candidates),
            "rejected_candidate_count": len(candidate_evaluations) - len(selected_candidates),
            "selected_coverage_ratio": round(
                len(selected_candidates) / len(candidate_evaluations), 4
            ) if candidate_evaluations else 0.0,
            "selection_status": (
                "needs-more-evidence"
                if not selected_candidates
                else "ready"
                if len(selected_candidates) == len(candidate_evaluations)
                else "partial"
            ),
            "selected_candidate_types": [
                item["candidate_type"] for item in selected_candidates
            ],
            "selected_candidate_profile_ids": [
                item["profile"]["profile_id"] for item in selected_candidates
            ],
        },
    }


def render_stable_writer_profile_evaluation_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Stable Writer Profile Evaluation",
        "",
        f"- base_profile_id: `{packet['base_profile_id']}`",
        f"- expected_input_texts: `{packet['expected_input_texts']}`",
        f"- expected_seeds: `{packet['expected_seeds']}`",
        f"- baseline_record_count: `{packet['baseline_record_count']}`",
        f"- candidate_count: `{packet['candidate_count']}`",
        f"- selected_profile_ids: `{packet['selected_profile_ids']}`",
        f"- selection_summary: `{packet['selection_summary']}`",
        "",
        "## Candidate Evaluations",
        "",
    ]
    if not packet["candidate_evaluations"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in packet["candidate_evaluations"]:
        evaluation = item["evaluation"]
        lines.extend(
            [
                f"### {item['candidate_type']}",
                "",
                f"- profile_id: `{item['profile']['profile_id']}`",
                f"- selected: `{item['selected']}`",
                f"- support_count: `{item['support_count']}`",
                f"- support_ratio: `{item['support_ratio']}`",
                f"- selection_reason: `{item['selection_reason']}`",
                f"- applied_changes: `{item['applied_changes']}`",
                f"- evaluation: `{evaluation}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def evaluate_data_driven_writer_prior_fixed_input_set(
    root: Path,
    *,
    samples_jsonl: str | Path,
    expected_input_texts: tuple[str, ...] = DEFAULT_STRUCTURE_INPUTS,
    expected_seeds: tuple[int, ...] = (1, 2, 3),
    base_profile_id: str = "baseline-neat",
) -> dict[str, Any]:
    estimate = estimate_writer_profile_from_jsonl(
        samples_jsonl,
        base_profile_id=base_profile_id,
    )
    derived_profile = estimate["profile"]
    registry = ExperimentRegistry(root / "registry.jsonl")
    base_profile = resolve_writer_profile(base_profile_id)

    baseline_records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(expected_input_texts, start=1):
        for seed in expected_seeds:
            baseline_records.append(
                _run_or_load_structure_motion(
                    root=root,
                    registry=registry,
                    experiment_id=_data_prior_experiment_id(
                        "baseline",
                        base_profile.profile_id,
                        input_index,
                        seed,
                    ),
                    input_text=input_text,
                    seed=seed,
                    writer_profile=base_profile,
                )
            )

    candidate_records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(expected_input_texts, start=1):
        for seed in expected_seeds:
            candidate_records.append(
                _run_or_load_structure_motion(
                    root=root,
                    registry=registry,
                    experiment_id=_data_prior_experiment_id(
                        "derived",
                        derived_profile.profile_id,
                        input_index,
                        seed,
                    ),
                    input_text=input_text,
                    seed=seed,
                    writer_profile=derived_profile,
                )
            )

    baseline_by_key = _records_by_input_and_seed(baseline_records)
    candidate_evaluation = _compare_against_profile_baseline(candidate_records, baseline_by_key)
    selected, selection_reason = _is_selected_data_prior_candidate(candidate_evaluation)

    return {
        "base_profile_id": base_profile_id,
        "samples_jsonl": str(samples_jsonl),
        "expected_input_texts": list(expected_input_texts),
        "expected_seeds": list(expected_seeds),
        "base_profile": base_profile.to_dict(),
        "derived_profile": derived_profile.to_dict(),
        "estimate": {
            "summary": estimate["summary"],
            "source": estimate["source"],
        },
        "baseline_record_count": len(baseline_records),
        "candidate_record_count": len(candidate_records),
        "comparison": candidate_evaluation,
        "selected": selected,
        "selection_reason": selection_reason,
        "selected_profile_id": derived_profile.profile_id if selected else "",
        "evaluation_summary": {
            "selection_status": "selected" if selected else "rejected",
            "candidate_count": 1,
            "selected_candidate_count": 1 if selected else 0,
            "resolved_failure_tag_count": candidate_evaluation["resolved_failure_tag_count"],
            "new_failure_tag_count": candidate_evaluation["new_failure_tag_count"],
            "safety_violation_count": candidate_evaluation["safety_violation_count"],
            "metric_delta_means": candidate_evaluation["metric_delta_means"],
        },
    }


def render_data_driven_writer_prior_evaluation_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Data-driven Writer Prior Evaluation",
        "",
        f"- base_profile_id: `{packet['base_profile_id']}`",
        f"- samples_jsonl: `{packet['samples_jsonl']}`",
        f"- expected_input_texts: `{packet['expected_input_texts']}`",
        f"- expected_seeds: `{packet['expected_seeds']}`",
        f"- selected: `{packet['selected']}`",
        f"- selected_profile_id: `{packet['selected_profile_id']}`",
        f"- selection_reason: `{packet['selection_reason']}`",
        "",
        "## Estimated Prior",
        "",
        f"- source: `{packet['estimate']['source']}`",
        f"- summary: `{packet['estimate']['summary']}`",
        "",
        "## Comparison",
        "",
        f"- comparison_count: `{packet['comparison']['comparison_count']}`",
        f"- resolved_failure_tag_count: `{packet['comparison']['resolved_failure_tag_count']}`",
        f"- new_failure_tag_count: `{packet['comparison']['new_failure_tag_count']}`",
        f"- safety_violation_count: `{packet['comparison']['safety_violation_count']}`",
        f"- metric_delta_means: `{packet['comparison']['metric_delta_means']}`",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_preview_revision_loop_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Preview Revision Loop",
        "",
        f"- baseline_generator: `{packet['baseline_generator']}`",
        f"- expected_input_texts: `{packet['expected_input_texts']}`",
        f"- expected_seeds: `{packet['expected_seeds']}`",
        f"- rerun_count: `{packet['rerun_count']}`",
        f"- comparison_summary: `{packet['comparison_summary']}`",
        f"- design_principles: `{packet['design_principles']}`",
        "",
        "## Before",
        "",
        f"- iteration_status: `{packet['before_iteration']['iteration_status']}`",
        f"- selected_candidate_count: `{packet['before_iteration']['selected_candidate_count']}`",
        f"- selected_coverage_ratio: `{packet['before_iteration']['selected_coverage_ratio']}`",
        f"- iteration_next_experiment_hints: `{packet['before_iteration']['iteration_next_experiment_hints']}`",
        "",
        "## Applications",
        "",
    ]
    if not packet["applications"]:
        lines.append("- none")
    for item in packet["applications"]:
        lines.extend(
            [
                f"### input={item['input_text']} seed={item['seed']}",
                "",
                f"- status: `{item['status']}`",
                f"- candidate_experiment_id: `{item.get('candidate_experiment_id', '')}`",
                f"- revision_experiment_id: `{item.get('revision_experiment_id', '')}`",
                f"- revision_profile_id: `{item.get('revision_profile_id', '')}`",
                f"- applied_changes: `{item.get('applied_changes', [])}`",
                f"- unapplied_changes: `{item.get('unapplied_changes', [])}`",
            ]
        )
        if item.get("comparison") is not None:
            comparison = item["comparison"]
            lines.extend(
                [
                    f"- comparison_metric_deltas: `{comparison['metric_deltas']}`",
                    f"- comparison_resolved_failure_tags: `{comparison['resolved_failure_tags']}`",
                    f"- comparison_new_failure_tags: `{comparison['new_failure_tags']}`",
                ]
            )
        if item.get("report"):
            lines.append(f"- report: `{item['report']}`")
        if item.get("preview"):
            lines.append(f"- preview: `{item['preview']}`")
        lines.append("")

    lines.extend(
        [
            "## After",
            "",
            f"- iteration_status: `{packet['after_iteration']['iteration_status']}`",
            f"- selected_candidate_count: `{packet['after_iteration']['selected_candidate_count']}`",
            f"- selected_coverage_ratio: `{packet['after_iteration']['selected_coverage_ratio']}`",
            f"- iteration_next_experiment_hints: `{packet['after_iteration']['iteration_next_experiment_hints']}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _compare_revision_outcome(
    candidate: ExperimentRecord,
    revision: ExperimentRecord,
) -> dict[str, Any]:
    metric_names = (
        "duration_ms",
        "velocity_peak_count",
        "draw_speed_cv",
        "mean_abs_jerk_mm_s3",
        "stroke_start_spacing_cv",
        "baseline_drift_mm",
        "shape_variation_mm",
        "layout_variation_mm",
        "repeated_char_ratio",
    )
    return {
        "candidate_experiment_id": candidate.experiment_id,
        "revision_experiment_id": revision.experiment_id,
        "metric_deltas": _metric_deltas(candidate, revision, metric_names),
        "resolved_failure_tags": sorted(
            set(candidate.failure_tags) - set(revision.failure_tags)
        ),
        "new_failure_tags": sorted(set(revision.failure_tags) - set(candidate.failure_tags)),
    }


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


def _summarize_comparisons(applications: list[dict[str, Any]]) -> dict[str, Any]:
    compared = [item["comparison"] for item in applications if item.get("comparison") is not None]
    metric_names = sorted(
        {
            name
            for item in compared
            for name in item["metric_deltas"].keys()
        }
    )
    resolved_tags = sorted({tag for item in compared for tag in item["resolved_failure_tags"]})
    new_tags = sorted({tag for item in compared for tag in item["new_failure_tags"]})
    return {
        "comparison_count": len(compared),
        "metric_names": metric_names,
        "resolved_failure_tags": resolved_tags,
        "new_failure_tags": new_tags,
    }


def _extract_design_principles(applications: list[dict[str, Any]]) -> list[str]:
    principles: list[str] = []
    for item in applications:
        if item.get("status") != "rerun":
            continue
        for change in item.get("applied_changes", []):
            principle = _principle_from_change(change)
            if principle and principle not in principles:
                principles.append(principle)
    return principles


def _principle_from_change(change: dict[str, Any]) -> str:
    target = str(change.get("target", ""))
    parameter = str(change.get("parameter", ""))
    if target == "motion" and parameter == "timing_jitter_cv":
        return "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
    if target == "layout" and parameter == "baseline_drift_mm":
        return "layout: 長文が機械的なら baseline_drift_mm を増やす"
    if target == "layout" and parameter == "spacing_mean_mm":
        return "layout: 字間が不自然なら spacing_mean_mm を調整する"
    if target == "dictionary" and parameter == "shape_variation":
        return "dictionary: 骨格が硬いなら shape_variation を増やす"
    if target == "profile" and parameter == "terminal_gains":
        return "profile: 終端差が弱いなら terminal_gains の対比を強める"
    if target == "profile" and parameter == "slant_deg":
        return "profile: 字形がフォント寄りなら slant_deg をずらす"
    if target == "safety":
        return "safety: 安全性違反は見た目評価の前に修正する"
    return ""


def _revision_profile_id(plan: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "candidate_experiment_id": plan["candidate_experiment_id"],
            "candidate_profile_id": plan["candidate_profile_id"],
            "input_text": plan["input_text"],
            "seed": plan["seed"],
            "changes": plan["proposed_changes"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return f"{plan['candidate_profile_id']}-rev-{hashlib.sha256(payload).hexdigest()[:8]}"


def _revision_experiment_id(
    plan: dict[str, Any],
    revision_profile_id: str,
    registry: ExperimentRegistry,
) -> str:
    payload = json.dumps(
        {
            "candidate_experiment_id": plan["candidate_experiment_id"],
            "input_text": plan["input_text"],
            "seed": plan["seed"],
            "revision_profile_id": revision_profile_id,
            "changes": plan["proposed_changes"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    base = f"{plan['candidate_experiment_id']}-rev-{hashlib.sha256(payload).hexdigest()[:8]}"
    existing = registry.ids()
    if base not in existing:
        return base

    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def _bump_counts(counts: dict[str, int], items: list[str]) -> None:
    for item in items:
        if not item:
            continue
        counts[item] = counts.get(item, 0) + 1


def _records_by_input_and_seed(records: list[ExperimentRecord]) -> dict[tuple[str, int], ExperimentRecord]:
    return {(record.input_text, record.seed): record for record in records}


def _compare_against_profile_baseline(
    candidate_records: list[ExperimentRecord],
    baseline_by_key: dict[tuple[str, int], ExperimentRecord],
) -> dict[str, Any]:
    metric_names = (
        "duration_ms",
        "velocity_peak_count",
        "draw_speed_cv",
        "mean_abs_jerk_mm_s3",
        "stroke_start_spacing_cv",
        "baseline_drift_mm",
        "shape_variation_mm",
        "layout_variation_mm",
        "repeated_char_ratio",
        "gcode_safety_ok",
        "gcode_safety_violation_count",
    )
    comparisons: list[dict[str, Any]] = []
    selected_count = 0
    resolved_failure_tag_count = 0
    new_failure_tag_count = 0
    safety_violation_count = 0
    metric_delta_sums: dict[str, float] = {}
    metric_delta_counts: dict[str, int] = {}
    for record in candidate_records:
        baseline = baseline_by_key[(record.input_text, record.seed)]
        resolved = sorted(set(baseline.failure_tags) - set(record.failure_tags))
        new = sorted(set(record.failure_tags) - set(baseline.failure_tags))
        if int(record.metrics.get("gcode_safety_violation_count", 0)) == 0:
            selected_count += 1
        resolved_failure_tag_count += len(resolved)
        new_failure_tag_count += len(new)
        safety_violation_count += int(record.metrics.get("gcode_safety_violation_count", 0))
        deltas = _metric_deltas(baseline, record, metric_names)
        for name, delta in deltas.items():
            metric_delta_sums[name] = metric_delta_sums.get(name, 0.0) + delta
            metric_delta_counts[name] = metric_delta_counts.get(name, 0) + 1
        comparisons.append(
            {
                "input_text": record.input_text,
                "seed": record.seed,
                "metric_deltas": deltas,
                "resolved_failure_tags": resolved,
                "new_failure_tags": new,
            }
        )

    return {
        "comparison_count": len(comparisons),
        "selected_count": selected_count,
        "resolved_failure_tag_count": resolved_failure_tag_count,
        "new_failure_tag_count": new_failure_tag_count,
        "safety_violation_count": safety_violation_count,
        "metric_delta_means": {
            name: round(metric_delta_sums[name] / metric_delta_counts[name], 4)
            for name in sorted(metric_delta_sums)
            if metric_delta_counts.get(name, 0)
        },
        "comparisons": comparisons,
    }


def _is_selected_stable_candidate(
    candidate: dict[str, Any],
    evaluation: dict[str, Any],
) -> tuple[bool, str]:
    if int(evaluation["safety_violation_count"]) > 0:
        return False, "safety violation count is non-zero"
    if int(evaluation["new_failure_tag_count"]) > 0:
        return False, "new failure tags remain"
    if int(evaluation["resolved_failure_tag_count"]) == 0:
        return False, "no baseline failure tags were resolved"
    if float(candidate.get("support_ratio", 0.0)) < 0.5:
        return False, "support ratio is below the acceptance threshold"
    return True, "selected"


def _is_selected_data_prior_candidate(evaluation: dict[str, Any]) -> tuple[bool, str]:
    if int(evaluation["safety_violation_count"]) > 0:
        return False, "safety violation count is non-zero"
    if int(evaluation["new_failure_tag_count"]) > 0:
        return False, "new failure tags remain"
    if int(evaluation["resolved_failure_tag_count"]) == 0:
        return False, "no baseline failure tags were resolved"
    return True, "selected"


def _run_or_load_structure_motion(
    *,
    root: Path,
    registry: ExperimentRegistry,
    experiment_id: str,
    input_text: str,
    seed: int,
    writer_profile: Any,
) -> ExperimentRecord:
    try:
        return registry.get(experiment_id)
    except KeyError:
        return run_structure_motion(
            root=root,
            experiment_id=experiment_id,
            input_text=input_text,
            seed=seed,
            writer_profile=writer_profile,
        )


def _profile_from_dict(data: dict[str, Any]):
    from writer_profile.models import WriterProfile, WriterProfileParameters

    params = WriterProfileParameters(**data["params"])
    return WriterProfile(
        profile_id=str(data["profile_id"]),
        version=int(data["version"]),
        source=str(data["source"]),
        allowed_use=str(data["allowed_use"]),
        params=params,
        parent_profile=data.get("parent_profile"),
        created_from_experiment=data.get("created_from_experiment"),
        notes=str(data.get("notes", "")),
    )


def _stable_profile_experiment_id(
    candidate_type: str,
    profile_id: str,
    input_index: int,
    seed: int,
) -> str:
    return f"exp-stable-{candidate_type[:4]}-{profile_id}-{input_index:02d}-s{seed:03d}"


def _data_prior_experiment_id(
    candidate_type: str,
    profile_id: str,
    input_index: int,
    seed: int,
) -> str:
    return f"exp-prior-{candidate_type[:4]}-{profile_id}-{input_index:02d}-s{seed:03d}"


def _build_stable_writer_profile_candidate(
    base_profile: Any,
    *,
    candidate_type: str,
    principles: list[str],
    support_counts: dict[str, int],
    packet_count: int,
    min_count: int,
) -> dict[str, Any] | None:
    if not principles:
        return None

    changes: list[dict[str, Any]] = []
    support_count = 0
    for principle in principles:
        change = _change_from_principle(principle)
        if change is None:
            continue
        if int(support_counts.get(principle, 0)) < min_count:
            continue
        changes.append(change)
        support_count = max(support_count, int(support_counts.get(principle, 0)))

    if not changes:
        return None

    revision = build_revision_profile(
        base_profile,
        changes,
        revision_profile_id=_stable_candidate_profile_id(base_profile.profile_id, candidate_type, principles),
        created_from_experiment=f"preview-revision-summary:{packet_count}",
    )
    profile = revision["profile"]
    return {
        "candidate_type": candidate_type,
        "principles": principles,
        "support_count": support_count,
        "support_ratio": round(support_count / packet_count, 4) if packet_count else 0.0,
        "applied_changes": list(revision["applied_changes"]),
        "unapplied_changes": list(revision["unapplied_changes"]),
        "profile": profile.to_dict(),
    }


def _change_from_principle(principle: str) -> dict[str, Any] | None:
    mapping = {
        "motion: 等速感が強いときは timing_jitter_cv を先に上げる": {
            "target": "motion",
            "parameter": "timing_jitter_cv",
            "direction": "increase",
            "amount_hint": 0.03,
            "reason": "等速感を減らし、速度ピークを作る",
        },
        "layout: 長文が機械的なら baseline_drift_mm を増やす": {
            "target": "layout",
            "parameter": "baseline_drift_mm",
            "direction": "increase",
            "amount_hint": 0.4,
            "reason": "行方向の機械的整列を崩す",
        },
        "layout: 字間が不自然なら spacing_mean_mm を調整する": {
            "target": "layout",
            "parameter": "spacing_mean_mm",
            "direction": "increase",
            "amount_hint": 0.15,
            "reason": "字間をわずかに広げる",
        },
        "dictionary: 骨格が硬いなら shape_variation を増やす": {
            "target": "dictionary",
            "parameter": "shape_variation",
            "direction": "increase",
            "amount_hint": 0.02,
            "reason": "字形の剛直さを和らげる",
        },
        "profile: 終端差が弱いなら terminal_gains の対比を強める": {
            "target": "profile",
            "parameter": "terminal_gains",
            "direction": "increase-contrast",
            "amount_hint": 0.1,
            "reason": "払い、はね、とめの終端差を強める",
        },
        "profile: 字形がフォント寄りなら slant_deg をずらす": {
            "target": "profile",
            "parameter": "slant_deg",
            "direction": "adjust",
            "amount_hint": 2.0,
            "reason": "字体から離して筆者寄りに寄せる",
        },
        "safety: 安全性違反は見た目評価の前に修正する": {
            "target": "safety",
            "parameter": "gcode_safety",
            "direction": "fix",
            "amount_hint": None,
            "reason": "安全性違反を解消してから再比較する",
        },
    }
    return mapping.get(principle)


def _stable_candidate_profile_id(
    base_profile_id: str,
    candidate_type: str,
    principles: list[str],
) -> str:
    payload = json.dumps(
        {
            "base_profile_id": base_profile_id,
            "candidate_type": candidate_type,
            "principles": principles,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return f"{base_profile_id}-{candidate_type}-{hashlib.sha256(payload).hexdigest()[:8]}"

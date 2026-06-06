from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation_harness.compare import preview_iteration_fixed_input_set
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.structure_motion import run_structure_motion
from evaluation_harness.writer_profile import build_revision_profile, resolve_writer_profile


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
        "after_iteration": after_iteration,
    }


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

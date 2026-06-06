from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation_harness.compare import preview_iteration_fixed_input_set
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

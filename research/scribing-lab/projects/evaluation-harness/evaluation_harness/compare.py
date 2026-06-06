from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.models import ExperimentRecord


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
                f"- baseline_preview: `{item['baseline_preview']}`",
                f"- candidate_preview: `{item['candidate_preview']}`",
                "",
            ]
        )
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
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        return None
    data = path.read_bytes()
    return {
        "path": str(path),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

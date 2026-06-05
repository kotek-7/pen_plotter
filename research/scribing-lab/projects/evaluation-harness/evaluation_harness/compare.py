from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

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

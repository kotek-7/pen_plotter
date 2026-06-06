from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from evaluation_harness.models import ExperimentRecord


@dataclass(frozen=True)
class OfflineReviewItem:
    experiment_id: str
    input_text: str
    seed: int
    generator: str
    existing_failure_tags: list[str]
    inferred_failure_tags: list[str]
    suggested_next_actions: list[str]
    evidence: dict[str, float | int | str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "input_text": self.input_text,
            "seed": self.seed,
            "generator": self.generator,
            "existing_failure_tags": list(self.existing_failure_tags),
            "inferred_failure_tags": list(self.inferred_failure_tags),
            "suggested_next_actions": list(self.suggested_next_actions),
            "evidence": dict(self.evidence),
        }


NEXT_ACTIONS: dict[str, str] = {
    "too-uniform": "motion-synthesis の speed profile / timing jitter を上げる",
    "line-too-mechanical": "layout の spacing / baseline drift を上げる",
    "over-jittered": "motion-synthesis の tremor / timing jitter を下げる",
    "plotter-unsafe": "G-code safety violations を解消してから scan 登録へ進む",
    "skeleton-too-rigid": "character-dictionary の shape variation を増やす",
    "terminal-too-uniform": "terminal pressure / finish mapping を強める",
    "too-font-like": "outline baseline ではなく structure 系候補を比較対象にする",
    "spacing-unnatural": "layout spacing のランダム化幅と行内整列を調整する",
    "repeated-char-too-identical": "同一文字の stroke template variant を増やす",
}


def infer_offline_failure_tags(record: ExperimentRecord) -> list[str]:
    tags: set[str] = set(record.failure_tags)
    metrics = record.metrics

    if _has_shape_variation(metrics):
        tags.discard("skeleton-too-rigid")
    if _has_layout_variation(metrics):
        tags.discard("line-too-mechanical")

    if _is_plotter_unsafe(metrics):
        tags.add("plotter-unsafe")

    if record.generator == "baseline-outline":
        tags.update({"too-font-like", "terminal-too-uniform"})
    elif record.generator in {"structure-uniform", "structure-motion"} and not _has_shape_variation(
        metrics
    ):
        tags.add("skeleton-too-rigid")

    if _looks_too_uniform(metrics):
        tags.add("too-uniform")

    if _looks_line_mechanical(record, metrics) and not _has_layout_variation(metrics):
        tags.add("line-too-mechanical")

    if _looks_over_jittered(metrics):
        tags.add("over-jittered")

    if _looks_repeated_too_identical(metrics):
        tags.add("repeated-char-too-identical")

    return sorted(tags)


def suggested_next_actions(tags: list[str]) -> list[str]:
    return [NEXT_ACTIONS[tag] for tag in tags if tag in NEXT_ACTIONS]


def review_record(record: ExperimentRecord) -> OfflineReviewItem:
    inferred_tags = infer_offline_failure_tags(record)
    return OfflineReviewItem(
        experiment_id=record.experiment_id,
        input_text=record.input_text,
        seed=record.seed,
        generator=record.generator,
        existing_failure_tags=list(record.failure_tags),
        inferred_failure_tags=inferred_tags,
        suggested_next_actions=suggested_next_actions(inferred_tags),
        evidence=_review_evidence(record),
    )


def build_offline_review(records: list[ExperimentRecord]) -> dict[str, Any]:
    items = [review_record(record) for record in sorted(records, key=_record_sort_key)]
    tag_counts = Counter(tag for item in items for tag in item.inferred_failure_tags)
    action_counts = Counter(action for item in items for action in item.suggested_next_actions)
    return {
        "record_count": len(items),
        "generator_counts": dict(Counter(item.generator for item in items)),
        "failure_tag_counts": dict(sorted(tag_counts.items())),
        "suggested_action_counts": dict(sorted(action_counts.items())),
        "robustness": _build_robustness_summary(records, items),
        "items": [item.to_dict() for item in items],
    }


def render_offline_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Offline Review",
        "",
        f"- record_count: `{review['record_count']}`",
        f"- generator_counts: `{review['generator_counts']}`",
        f"- failure_tag_counts: `{review['failure_tag_counts']}`",
        f"- suggested_action_counts: `{review['suggested_action_counts']}`",
        f"- robustness: `{review['robustness']}`",
        "",
        "## Records",
        "",
    ]
    if not review["items"]:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in review["items"]:
        lines.extend(
            [
                f"### {item['experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- generator: `{item['generator']}`",
                f"- existing_failure_tags: `{item['existing_failure_tags']}`",
                f"- inferred_failure_tags: `{item['inferred_failure_tags']}`",
                f"- evidence: `{item['evidence']}`",
                "- suggested_next_actions:",
            ]
        )
        if item["suggested_next_actions"]:
            lines.extend(f"  - {action}" for action in item["suggested_next_actions"])
        else:
            lines.append("  - none")
        lines.append("")
    return "\n".join(lines) + "\n"


def _is_plotter_unsafe(metrics: dict[str, float | int | str]) -> bool:
    if "gcode_safety_ok" in metrics and int(metrics["gcode_safety_ok"]) != 1:
        return True
    return int(metrics.get("gcode_safety_violation_count", 0)) > 0


def _looks_too_uniform(metrics: dict[str, float | int | str]) -> bool:
    velocity_peaks = int(metrics.get("velocity_peak_count", 0))
    draw_speed_cv = float(metrics.get("draw_speed_cv", 0.0))
    point_count = int(metrics.get("point_count", 0))
    if point_count < 4:
        return False
    return velocity_peaks == 0 or draw_speed_cv < 0.05


def _has_shape_variation(metrics: dict[str, float | int | str]) -> bool:
    return float(metrics.get("shape_variation_mm", 0.0)) >= 0.5


def _has_layout_variation(metrics: dict[str, float | int | str]) -> bool:
    return float(metrics.get("layout_variation_mm", 0.0)) >= 0.5


def _looks_line_mechanical(
    record: ExperimentRecord,
    metrics: dict[str, float | int | str],
) -> bool:
    visible_chars = int(metrics.get("visible_char_count", len(record.input_text)))
    if visible_chars < 5:
        return False
    spacing_cv = float(metrics.get("stroke_start_spacing_cv", 0.0))
    baseline_drift = float(metrics.get("baseline_drift_mm", 0.0))
    return spacing_cv < 0.05 and baseline_drift < 1.0


def _looks_over_jittered(metrics: dict[str, float | int | str]) -> bool:
    return (
        float(metrics.get("draw_speed_cv", 0.0)) > 1.2
        or float(metrics.get("mean_abs_jerk_mm_s3", 0.0)) > 50000.0
    )


def _looks_repeated_too_identical(metrics: dict[str, float | int | str]) -> bool:
    return (
        float(metrics.get("repeated_char_ratio", 0.0)) > 0.0
        and float(metrics.get("stroke_start_spacing_cv", 0.0)) < 0.03
        and float(metrics.get("baseline_drift_mm", 0.0)) < 0.5
    )


def _review_evidence(record: ExperimentRecord) -> dict[str, float | int | str]:
    keys = (
        "point_count",
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
    return {key: record.metrics[key] for key in keys if key in record.metrics}


def _build_robustness_summary(
    records: list[ExperimentRecord],
    items: list[OfflineReviewItem],
) -> dict[str, Any]:
    unsafe_records = [
        record.experiment_id
        for record in records
        if _is_plotter_unsafe(record.metrics)
    ]
    failing_items = [
        item.experiment_id
        for item in items
        if item.inferred_failure_tags
    ]
    repeated_inputs = sorted(
        {
            record.input_text
            for record in records
            if float(record.metrics.get("repeated_char_ratio", 0.0)) > 0.0
        }
    )
    return {
        "input_count": len({record.input_text for record in records}),
        "seed_count": len({record.seed for record in records}),
        "failing_record_count": len(failing_items),
        "unsafe_record_count": len(unsafe_records),
        "repeated_input_count": len(repeated_inputs),
        "unstable_metric_groups": _unstable_metric_groups(records),
        "status": "ok" if not failing_items and not unsafe_records else "needs-review",
    }


def _unstable_metric_groups(records: list[ExperimentRecord]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[ExperimentRecord]] = {}
    for record in records:
        groups.setdefault((record.generator, record.input_text), []).append(record)

    unstable: list[dict[str, Any]] = []
    for (generator, input_text), group in sorted(groups.items()):
        if len({record.seed for record in group}) < 3:
            continue
        for metric_name, threshold in (
            ("draw_speed_cv", 0.35),
            ("mean_abs_jerk_mm_s3", 30000.0),
            ("baseline_drift_mm", 4.0),
        ):
            values = [
                float(record.metrics[metric_name])
                for record in group
                if isinstance(record.metrics.get(metric_name), (int, float))
            ]
            if len(values) < 3:
                continue
            value_range = max(values) - min(values)
            if value_range > threshold:
                unstable.append(
                    {
                        "generator": generator,
                        "input_text": input_text,
                        "metric": metric_name,
                        "range": round(value_range, 4),
                    }
                )
    return unstable


def _record_sort_key(record: ExperimentRecord) -> tuple[str, int, str, str]:
    return (record.input_text, record.seed, record.generator, record.experiment_id)

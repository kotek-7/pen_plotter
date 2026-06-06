from __future__ import annotations

from typing import Any

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import build_offline_review


KEY_METRICS: tuple[str, ...] = (
    "draw_speed_cv",
    "mean_abs_jerk_mm_s3",
    "stroke_start_spacing_cv",
    "baseline_drift_mm",
    "repeated_char_ratio",
    "shape_variation_mm",
    "layout_variation_mm",
    "gcode_safety_ok",
    "gcode_safety_violation_count",
)


def build_human_review_packet(records: list[ExperimentRecord]) -> dict[str, Any]:
    review = build_offline_review(records)
    by_id = {record.experiment_id: record for record in records}
    representative_ids = _select_representative_ids(records, review)
    representative_records = [by_id[experiment_id] for experiment_id in representative_ids]
    return {
        "record_count": len(records),
        "robustness": review["robustness"],
        "failure_tag_counts": review["failure_tag_counts"],
        "representative_count": len(representative_records),
        "representatives": [
            _packet_item(record, reason=_representative_reason(record, review))
            for record in representative_records
        ],
        "records_by_input": _records_by_input(records),
    }


def render_human_review_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Human Review Packet",
        "",
        f"- record_count: `{packet['record_count']}`",
        f"- representative_count: `{packet['representative_count']}`",
        f"- failure_tag_counts: `{packet['failure_tag_counts']}`",
        f"- robustness: `{packet['robustness']}`",
        "",
        "## Representatives",
        "",
    ]
    if not packet["representatives"]:
        lines.append("- none")
    for item in packet["representatives"]:
        lines.extend(
            [
                f"### {item['experiment_id']}",
                "",
                f"- reason: `{item['reason']}`",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- preview: `{item['preview']}`",
                f"- failure_tags: `{item['failure_tags']}`",
                f"- metrics: `{item['metrics']}`",
                "",
            ]
        )

    lines.extend(["## Records By Input", ""])
    for input_text, items in packet["records_by_input"].items():
        lines.extend([f"### {input_text}", ""])
        for item in items:
            lines.append(
                "- "
                f"{item['experiment_id']}: "
                f"seed=`{item['seed']}`, "
                f"preview=`{item['preview']}`, "
                f"failure_tags=`{item['failure_tags']}`"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _select_representative_ids(
    records: list[ExperimentRecord],
    review: dict[str, Any],
) -> list[str]:
    selected: list[str] = []

    for experiment_id in review.get("robustness", {}).get("uncertain_record_ids", []):
        _append_unique(selected, experiment_id)

    for item in review["items"]:
        if item["inferred_failure_tags"]:
            _append_unique(selected, item["experiment_id"])

    repeated = [
        record
        for record in records
        if float(record.metrics.get("repeated_char_ratio", 0.0)) > 0.0
    ]
    if repeated:
        _append_unique(selected, _max_metric_record(repeated, "repeated_char_ratio").experiment_id)

    newline = [record for record in records if "\n" in record.input_text]
    if newline:
        _append_unique(selected, _max_metric_record(newline, "baseline_drift_mm").experiment_id)

    if records:
        _append_unique(selected, _max_metric_record(records, "mean_abs_jerk_mm_s3").experiment_id)
        _append_unique(selected, _min_metric_record(records, "draw_speed_cv").experiment_id)
        _append_unique(selected, _max_metric_record(records, "draw_speed_cv").experiment_id)

    target_count = _target_representative_count(len(records))
    if len(selected) < target_count:
        ranked_ids = [
            str(item["experiment_id"])
            for item in sorted(
                review.get("items", []),
                key=lambda item: (
                    -float(item.get("risk_score", 0.0)),
                    float(item.get("confidence", 0.0)),
                    str(item.get("experiment_id", "")),
                ),
            )
        ]
        for experiment_id in ranked_ids:
            _append_unique(selected, experiment_id)
            if len(selected) >= target_count:
                break

    return selected[:target_count]


def _target_representative_count(record_count: int) -> int:
    if record_count <= 0:
        return 0
    target = max(12, record_count // 2)
    target = min(target, 36)
    return target


def _representative_reason(record: ExperimentRecord, review: dict[str, Any]) -> str:
    for item in review["items"]:
        if item["experiment_id"] == record.experiment_id and item["inferred_failure_tags"]:
            return "failure-tag"
    if float(record.metrics.get("repeated_char_ratio", 0.0)) > 0.0:
        return "repeated-input"
    if "\n" in record.input_text:
        return "newline-input"
    return "metric-extreme"


def _records_by_input(records: list[ExperimentRecord]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in sorted(records, key=lambda item: (item.input_text, item.seed, item.experiment_id)):
        grouped.setdefault(record.input_text, []).append(_packet_item(record, reason="input-group"))
    return grouped


def _packet_item(record: ExperimentRecord, *, reason: str) -> dict[str, Any]:
    return {
        "experiment_id": record.experiment_id,
        "input_text": record.input_text,
        "seed": record.seed,
        "reason": reason,
        "preview": record.artifacts.get("preview", ""),
        "failure_tags": list(record.failure_tags),
        "metrics": {
            name: record.metrics[name]
            for name in KEY_METRICS
            if name in record.metrics
        },
    }


def _max_metric_record(records: list[ExperimentRecord], metric_name: str) -> ExperimentRecord:
    return max(records, key=lambda record: float(record.metrics.get(metric_name, 0.0)))


def _min_metric_record(records: list[ExperimentRecord], metric_name: str) -> ExperimentRecord:
    return min(records, key=lambda record: float(record.metrics.get(metric_name, 0.0)))


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)

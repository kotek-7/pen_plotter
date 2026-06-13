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

SCRIPT_GROUP_PRIORITY: tuple[str, ...] = (
    "kana",
    "kanji",
    "latin",
    "digit",
    "punctuation",
    "symbol",
    "other",
)


def build_human_review_packet(
    records: list[ExperimentRecord],
    *,
    target_count: int | None = None,
    sort_order: str = "default",
) -> dict[str, Any]:
    review = build_offline_review(records)
    by_id = {record.experiment_id: record for record in records}
    representative_ids = _select_representative_ids(
        records,
        review,
        target_count=target_count,
    )
    representative_ids = _sort_representative_ids(
        representative_ids,
        by_id,
        sort_order=sort_order,
    )
    representative_records = [by_id[experiment_id] for experiment_id in representative_ids]
    return {
        "record_count": len(records),
        "robustness": review["robustness"],
        "failure_tag_counts": review["failure_tag_counts"],
        "script_group_counts": _script_group_counts(records),
        "representative_count": len(representative_records),
        "representatives": [
            _packet_item(record, reason=_representative_reason(record, review))
            for record in representative_records
        ],
        "records_by_input": _records_by_input(records, sort_order=sort_order),
        "sort_order": sort_order,
    }


def render_human_review_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Human Review Packet",
        "",
        f"- record_count: `{packet['record_count']}`",
        f"- representative_count: `{packet['representative_count']}`",
        f"- failure_tag_counts: `{packet['failure_tag_counts']}`",
        f"- script_group_counts: `{packet.get('script_group_counts', {})}`",
        f"- sort_order: `{packet.get('sort_order', 'default')}`",
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
                f"- input_script_groups: `{item.get('input_script_groups', [])}`",
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
                f"script_groups=`{item.get('input_script_groups', [])}`, "
                f"preview=`{item['preview']}`, "
                f"failure_tags=`{item['failure_tags']}`"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _select_representative_ids(
    records: list[ExperimentRecord],
    review: dict[str, Any],
    *,
    target_count: int | None = None,
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

    selected_groups = _covered_script_groups(records, selected)
    for group in SCRIPT_GROUP_PRIORITY:
        if group in selected_groups:
            continue
        candidate = _best_record_for_script_group(records, review, group)
        if candidate is None:
            continue
        _append_unique(selected, candidate.experiment_id)
        selected_groups.update(_input_script_groups(candidate.input_text))

    target_count = _target_representative_count(len(records), target_count=target_count)
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


def _target_representative_count(record_count: int, *, target_count: int | None = None) -> int:
    if record_count <= 0:
        return 0
    if target_count is not None:
        return max(1, min(int(target_count), record_count))
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


def _records_by_input(
    records: list[ExperimentRecord],
    *,
    sort_order: str = "default",
) -> dict[str, list[dict[str, Any]]]:
    ordered_records = sorted(
        records,
        key=lambda item: _record_sort_key(item, sort_order=sort_order),
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in ordered_records:
        grouped.setdefault(record.input_text, []).append(_packet_item(record, reason="input-group"))
    return grouped


def _sort_representative_ids(
    representative_ids: list[str],
    by_id: dict[str, ExperimentRecord],
    *,
    sort_order: str,
) -> list[str]:
    if sort_order != "longform-first":
        return representative_ids
    return sorted(
        representative_ids,
        key=lambda experiment_id: _record_sort_key(by_id[experiment_id], sort_order=sort_order),
    )


def _record_sort_key(record: ExperimentRecord, *, sort_order: str) -> tuple[Any, ...]:
    if sort_order == "longform-first":
        return (
            -len(record.input_text),
            -len(_input_script_groups(record.input_text)),
            record.input_text,
            record.seed,
            record.experiment_id,
        )
    return (record.input_text, record.seed, record.experiment_id)


def _packet_item(record: ExperimentRecord, *, reason: str) -> dict[str, Any]:
    return {
        "experiment_id": record.experiment_id,
        "input_text": record.input_text,
        "input_script_groups": list(_input_script_groups(record.input_text)),
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


def _best_record_for_script_group(
    records: list[ExperimentRecord],
    review: dict[str, Any],
    script_group: str,
) -> ExperimentRecord | None:
    review_by_id = {str(item["experiment_id"]): item for item in review.get("items", [])}
    candidates = [
        record
        for record in records
        if script_group in _input_script_groups(record.input_text)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: _script_group_rank_key(record, review_by_id))


def _script_group_rank_key(
    record: ExperimentRecord,
    review_by_id: dict[str, dict[str, Any]],
) -> tuple[float, float, int, str]:
    review_item = review_by_id.get(record.experiment_id, {})
    return (
        float(review_item.get("risk_score", 0.0)),
        -float(review_item.get("confidence", 0.0)),
        -len(_input_script_groups(record.input_text)),
        record.experiment_id,
    )


def _covered_script_groups(
    records: list[ExperimentRecord],
    selected_ids: list[str],
) -> set[str]:
    selected_by_id = {record.experiment_id: record for record in records}
    groups: set[str] = set()
    for experiment_id in selected_ids:
        record = selected_by_id.get(experiment_id)
        if record is None:
            continue
        groups.update(_input_script_groups(record.input_text))
    return groups


def _input_script_groups(text: str) -> tuple[str, ...]:
    groups: list[str] = []
    for char in text:
        group = _classify_character(char)
        if group not in groups:
            groups.append(group)
    if not groups:
        return ("other",)
    ordered = [group for group in SCRIPT_GROUP_PRIORITY if group in groups]
    return tuple(ordered or ["other"])


def _script_group_counts(records: list[ExperimentRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for group in _input_script_groups(record.input_text):
            counts[group] = counts.get(group, 0) + 1
    return counts


def _classify_character(char: str) -> str:
    if not char or char.isspace():
        return "other"
    if "0" <= char <= "9":
        return "digit"
    if "A" <= char <= "Z" or "a" <= char <= "z":
        return "latin"
    if "ぁ" <= char <= "ゟ" or "ァ" <= char <= "ヿ":
        return "kana"
    if "一" <= char <= "龯":
        return "kanji"
    if char in "。、，．！？「」『』・ー,.;:!?-()[]{}<>/\\":
        return "punctuation"
    if char in "@#$%&*+=~^_|`'\"":
        return "symbol"
    return "other"

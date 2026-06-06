from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.taxonomy import (
    describe_failure_tag,
    evidence_keys_for_failure_tag,
    failure_tag_group,
    group_failure_tags,
    normalize_evidence,
)


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
    tag_groups: dict[str, list[str]]
    rule_hits: list[dict[str, Any]]
    risk_score: float
    confidence: float

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
            "tag_groups": {k: list(v) for k, v in self.tag_groups.items()},
            "rule_hits": list(self.rule_hits),
            "risk_score": self.risk_score,
            "confidence": self.confidence,
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
    "too-small": "layout size と preview scale を大きくして可読域を確保する",
    "spacing-too-wide": "character advance と line spacing を詰める",
    "glyph-orientation-odd": "stroke direction と component orientation を確認する",
}


def _evaluate_offline_rules(record: ExperimentRecord) -> list[dict[str, Any]]:
    metrics = record.metrics
    hits: list[dict[str, Any]] = []

    def add_hit(tag: str, *, reason: str, score: float, evidence: dict[str, Any]) -> None:
        hits.append(
            {
                "tag": tag,
                "group": failure_tag_group(tag),
                "description": describe_failure_tag(tag),
                "reason": reason,
                "score": round(score, 4),
                "evidence": normalize_evidence(evidence, evidence_keys_for_failure_tag(tag)),
            }
        )

    if _is_plotter_unsafe(metrics):
        add_hit(
            "plotter-unsafe",
            reason="G-code 安全性違反または未安全",
            score=1.0,
            evidence=metrics,
        )

    if record.generator == "baseline-outline":
        add_hit(
            "too-font-like",
            reason="baseline-outline は比較基準としてフォント寄りになる",
            score=0.9,
            evidence=metrics,
        )
        add_hit(
            "terminal-too-uniform",
            reason="baseline-outline は終端差が弱い比較基準になる",
            score=0.8,
            evidence=metrics,
        )
    elif record.generator in {"structure-uniform", "structure-motion"} and not _has_shape_variation(
        metrics
    ):
        add_hit(
            "skeleton-too-rigid",
            reason="structure 系で shape variation が弱い",
            score=0.7,
            evidence=metrics,
        )

    if _looks_too_uniform(metrics):
        add_hit(
            "too-uniform",
            reason="速度ピーク不足または draw_speed_cv が低い",
            score=max(
                0.5,
                1.0 - min(float(metrics.get("draw_speed_cv", 0.0)) * 10.0, 1.0),
            ),
            evidence=metrics,
        )

    if _looks_line_mechanical(record, metrics) and not _has_layout_variation(metrics):
        add_hit(
            "line-too-mechanical",
            reason="字間と baseline drift が機械的",
            score=0.8,
            evidence=metrics,
        )

    if _looks_over_jittered(metrics):
        add_hit(
            "over-jittered",
            reason="速度変動または jerk が大きすぎる",
            score=0.9,
            evidence=metrics,
        )

    if _looks_repeated_too_identical(metrics):
        add_hit(
            "repeated-char-too-identical",
            reason="反復文字の差分が小さすぎる",
            score=0.75,
            evidence=metrics,
        )

    if _looks_too_small(metrics):
        add_hit(
            "too-small",
            reason="bbox が可読閾値を下回る",
            score=0.85,
            evidence=metrics,
        )

    if _looks_spacing_too_wide(metrics):
        add_hit(
            "spacing-too-wide",
            reason="字間または stroke gap が広すぎる",
            score=0.7,
            evidence=metrics,
        )

    if _looks_glyph_orientation_odd(metrics):
        add_hit(
            "glyph-orientation-odd",
            reason="小さい文字で aspect ratio が不自然",
            score=0.6,
            evidence=metrics,
        )

    if _looks_spacing_unnatural(metrics):
        add_hit(
            "spacing-unnatural",
            reason="字間・行間・配置の揺れが不自然",
            score=0.65,
            evidence=metrics,
        )

    return hits


def infer_offline_failure_tags(record: ExperimentRecord) -> list[str]:
    tags: set[str] = set(record.failure_tags)
    metrics = record.metrics

    if _has_shape_variation(metrics):
        tags.discard("skeleton-too-rigid")
    if _has_layout_variation(metrics):
        tags.discard("line-too-mechanical")

    tags.update(hit["tag"] for hit in _evaluate_offline_rules(record))
    return sorted(tags)


def suggested_next_actions(tags: list[str]) -> list[str]:
    return [NEXT_ACTIONS[tag] for tag in tags if tag in NEXT_ACTIONS]


def review_record(record: ExperimentRecord) -> OfflineReviewItem:
    rule_hits = _evaluate_offline_rules(record)
    inferred_tags = sorted(set(record.failure_tags) | {hit["tag"] for hit in rule_hits})
    tag_groups = group_failure_tags(inferred_tags)
    evidence = _review_evidence(record)
    risk_score = _risk_score(inferred_tags, evidence)
    confidence = _inference_confidence(rule_hits, evidence)
    return OfflineReviewItem(
        experiment_id=record.experiment_id,
        input_text=record.input_text,
        seed=record.seed,
        generator=record.generator,
        existing_failure_tags=list(record.failure_tags),
        inferred_failure_tags=inferred_tags,
        suggested_next_actions=suggested_next_actions(inferred_tags),
        evidence=evidence,
        tag_groups=tag_groups,
        rule_hits=rule_hits,
        risk_score=risk_score,
        confidence=confidence,
    )


def build_offline_review(records: list[ExperimentRecord]) -> dict[str, Any]:
    items = [review_record(record) for record in sorted(records, key=_record_sort_key)]
    tag_counts = Counter(tag for item in items for tag in item.inferred_failure_tags)
    action_counts = Counter(action for item in items for action in item.suggested_next_actions)
    group_counts = Counter(group for item in items for group in item.tag_groups)
    return {
        "record_count": len(items),
        "generator_counts": dict(Counter(item.generator for item in items)),
        "failure_tag_counts": dict(sorted(tag_counts.items())),
        "failure_tag_group_counts": dict(sorted(group_counts.items())),
        "suggested_action_counts": dict(sorted(action_counts.items())),
        "robustness": _build_robustness_summary(records, items),
        "mean_risk_score": round(sum(item.risk_score for item in items) / len(items), 4)
        if items
        else 0.0,
        "mean_confidence": round(sum(item.confidence for item in items) / len(items), 4)
        if items
        else 0.0,
        "items": [item.to_dict() for item in items],
    }


def render_offline_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Offline Review",
        "",
        f"- record_count: `{review['record_count']}`",
        f"- generator_counts: `{review['generator_counts']}`",
        f"- failure_tag_counts: `{review['failure_tag_counts']}`",
        f"- failure_tag_group_counts: `{review['failure_tag_group_counts']}`",
        f"- suggested_action_counts: `{review['suggested_action_counts']}`",
        f"- mean_risk_score: `{review['mean_risk_score']}`",
        f"- mean_confidence: `{review['mean_confidence']}`",
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
                f"- tag_groups: `{item['tag_groups']}`",
                f"- risk_score: `{item['risk_score']}`",
                f"- confidence: `{item['confidence']}`",
                f"- evidence: `{item['evidence']}`",
                f"- rule_hits: `{item['rule_hits']}`",
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


def _looks_too_small(metrics: dict[str, float | int | str]) -> bool:
    visible_chars = int(metrics.get("visible_char_count", 0))
    if visible_chars <= 0:
        return False
    if "ink_bbox_width_mm" not in metrics or "ink_bbox_height_mm" not in metrics:
        return False
    line_count = max(int(metrics.get("line_count", 1)), 1)
    bbox_width = float(metrics.get("ink_bbox_width_mm", 0.0))
    bbox_height = float(metrics.get("ink_bbox_height_mm", 0.0))
    if bbox_width <= 0.0 or bbox_height <= 0.0:
        return False
    mean_char_advance = bbox_width / max(visible_chars, 1)
    mean_line_height = bbox_height / line_count
    return mean_char_advance < 4.5 or mean_line_height < 7.5 or bbox_height < 8.5


def _looks_spacing_too_wide(metrics: dict[str, float | int | str]) -> bool:
    visible_chars = int(metrics.get("visible_char_count", 0))
    if visible_chars < 2:
        return False
    if "ink_bbox_width_mm" not in metrics:
        return False
    bbox_width = float(metrics.get("ink_bbox_width_mm", 0.0))
    if bbox_width <= 0.0:
        return False
    mean_char_advance = bbox_width / max(visible_chars, 1)
    mean_stroke_gap = float(metrics.get("mean_stroke_start_gap_mm", 0.0))
    return mean_char_advance > 13.5 or mean_stroke_gap > 14.0


def _looks_glyph_orientation_odd(metrics: dict[str, float | int | str]) -> bool:
    visible_chars = int(metrics.get("visible_char_count", 0))
    if visible_chars > 3:
        return False
    if "ink_bbox_width_mm" not in metrics or "ink_bbox_height_mm" not in metrics:
        return False
    bbox_width = float(metrics.get("ink_bbox_width_mm", 0.0))
    bbox_height = float(metrics.get("ink_bbox_height_mm", 0.0))
    if bbox_width <= 0.0 or bbox_height <= 0.0:
        return False
    aspect_ratio = float(metrics.get("ink_bbox_aspect_ratio", bbox_width / bbox_height))
    return aspect_ratio < 0.32


def _looks_spacing_unnatural(metrics: dict[str, float | int | str]) -> bool:
    spacing_cv = float(metrics.get("stroke_start_spacing_cv", 0.0))
    baseline_drift = float(metrics.get("baseline_drift_mm", 0.0))
    mean_gap = float(metrics.get("mean_stroke_start_gap_mm", 0.0))
    return (
        spacing_cv > 1.4
        or baseline_drift > 6.0
        or mean_gap > 20.0
        or (spacing_cv < 0.08 and baseline_drift < 0.5 and mean_gap > 10.0)
    )


def _risk_score(tags: list[str], evidence: dict[str, float | int | str]) -> float:
    if not tags:
        return 0.0
    weighted = 0.0
    for tag in tags:
        weighted += {
            "plotter-unsafe": 1.0,
            "unreadable": 0.95,
            "wrong-stroke-order": 0.85,
            "too-small": 0.8,
            "too-font-like": 0.7,
            "skeleton-too-rigid": 0.7,
            "line-too-mechanical": 0.6,
            "spacing-unnatural": 0.6,
            "spacing-too-wide": 0.55,
            "too-uniform": 0.55,
            "over-jittered": 0.75,
            "repeated-char-too-identical": 0.45,
            "glyph-orientation-odd": 0.55,
            "terminal-too-uniform": 0.4,
            "penup-artifact": 0.5,
            "scan-mismatch": 0.7,
            "plotter-line-quality-bad": 0.75,
            "profile-inconsistent": 0.4,
        }.get(tag, 0.3)
    if evidence.get("gcode_safety_ok", 1) == 0:
        weighted += 0.2
    if float(evidence.get("draw_speed_cv", 0.0)) > 0.8:
        weighted += 0.1
    return round(min(1.0, weighted / max(len(tags), 1)), 4)


def _inference_confidence(
    rule_hits: list[dict[str, Any]],
    evidence: dict[str, float | int | str],
) -> float:
    if not rule_hits:
        return 0.0
    score_sum = sum(float(hit.get("score", 0.0)) for hit in rule_hits)
    evidence_bonus = 0.0
    if evidence.get("gcode_safety_ok", 1) == 0:
        evidence_bonus += 0.1
    if "shape_variation_mm" in evidence:
        evidence_bonus += 0.05
    if "stroke_start_spacing_cv" in evidence:
        evidence_bonus += 0.05
    return round(min(1.0, score_sum / len(rule_hits) + evidence_bonus), 4)


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
    uncertain_record_ids = [
        item.experiment_id
        for item in items
        if item.confidence <= 0.35 or 0.25 <= item.risk_score <= 0.6
    ]
    return {
        "input_count": len({record.input_text for record in records}),
        "seed_count": len({record.seed for record in records}),
        "failing_record_count": len(failing_items),
        "unsafe_record_count": len(unsafe_records),
        "repeated_input_count": len(repeated_inputs),
        "uncertain_record_ids": uncertain_record_ids,
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

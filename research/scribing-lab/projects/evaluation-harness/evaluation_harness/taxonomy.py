from __future__ import annotations

from typing import Any


FAILURE_TAG_GROUPS: dict[str, frozenset[str]] = {
    "safety": frozenset({"plotter-unsafe", "scan-mismatch", "plotter-line-quality-bad"}),
    "motion": frozenset({"too-uniform", "over-jittered", "terminal-too-uniform", "penup-artifact"}),
    "layout": frozenset(
        {"spacing-unnatural", "line-too-mechanical", "paragraph-spacing-unnatural", "spacing-too-wide"}
    ),
    "shape": frozenset({"too-font-like", "skeleton-too-rigid", "glyph-orientation-odd"}),
    "consistency": frozenset({"repeated-char-too-identical", "profile-inconsistent"}),
    "readability": frozenset({"too-small", "unreadable", "wrong-stroke-order"}),
}

FAILURE_TAG_DESCRIPTIONS: dict[str, str] = {
    "unreadable": "読めない、または文字の崩れが大きい。",
    "wrong-stroke-order": "筆順や画の順序が不自然。",
    "too-uniform": "速度や形が均一で機械的。",
    "over-jittered": "揺れが強すぎて線が荒れている。",
    "spacing-unnatural": "字間・行間・配置が不自然。",
    "terminal-too-uniform": "終筆の抜きが硬く、差が弱い。",
    "penup-artifact": "ペンアップ移動が痕跡として見える。",
    "plotter-unsafe": "実機制約に対して危険または不適切。",
    "profile-inconsistent": "同一 profile でも挙動が一貫しない。",
    "too-font-like": "手書きよりフォント輪郭に寄っている。",
    "too-small": "小さすぎて可読性が不足する。",
    "skeleton-too-rigid": "骨格が硬すぎて可変性がない。",
    "line-too-mechanical": "行全体が機械的に整列しすぎている。",
    "paragraph-spacing-unnatural": "段落の空きや密度が不自然。",
    "spacing-too-wide": "字間が広すぎる。",
    "repeated-char-too-identical": "反復文字が同一化しすぎている。",
    "glyph-orientation-odd": "文字の向きや部品の向きが変。",
    "scan-mismatch": "実機スキャンと preview の差が大きい。",
    "plotter-line-quality-bad": "実機の線質が悪い。",
}

FAILURE_TAGS: frozenset[str] = frozenset(FAILURE_TAG_DESCRIPTIONS)

FAILURE_TAG_EVIDENCE_KEYS: dict[str, tuple[str, ...]] = {
    "unreadable": ("visible_char_count", "ink_bbox_area_mm2"),
    "wrong-stroke-order": ("point_count", "stroke_count"),
    "too-uniform": ("velocity_peak_count", "draw_speed_cv"),
    "over-jittered": ("draw_speed_cv", "mean_abs_jerk_mm_s3"),
    "spacing-unnatural": ("stroke_start_spacing_cv", "baseline_drift_mm"),
    "terminal-too-uniform": ("terminal_variation", "shape_variation_mm"),
    "penup-artifact": ("penup_distance_mm", "gcode_safety_violation_count"),
    "plotter-unsafe": ("gcode_safety_ok", "gcode_safety_violation_count"),
    "profile-inconsistent": ("profile_id", "seed"),
    "too-font-like": ("shape_variation_mm", "ink_bbox_aspect_ratio"),
    "too-small": ("ink_bbox_width_mm", "ink_bbox_height_mm"),
    "skeleton-too-rigid": ("shape_variation_mm", "repeated_char_ratio"),
    "line-too-mechanical": ("stroke_start_spacing_cv", "baseline_drift_mm"),
    "paragraph-spacing-unnatural": ("line_count", "baseline_drift_mm"),
    "spacing-too-wide": ("mean_stroke_start_gap_mm", "ink_bbox_width_mm"),
    "repeated-char-too-identical": ("repeated_char_ratio", "stroke_start_spacing_cv"),
    "glyph-orientation-odd": ("ink_bbox_aspect_ratio", "visible_char_count"),
    "scan-mismatch": ("preview_similarity", "scan_similarity"),
    "plotter-line-quality-bad": ("gcode_safety_violation_count", "mean_abs_jerk_mm_s3"),
}


def validate_failure_tags(tags: list[str]) -> None:
    unknown = sorted(set(tags) - FAILURE_TAGS)
    if unknown:
        raise ValueError(f"Unknown failure tags: {', '.join(unknown)}")


def failure_tag_group(tag: str) -> str:
    for group_name, group_tags in FAILURE_TAG_GROUPS.items():
        if tag in group_tags:
            return group_name
    return "other"


def describe_failure_tag(tag: str) -> str:
    return FAILURE_TAG_DESCRIPTIONS.get(tag, "")


def evidence_keys_for_failure_tag(tag: str) -> tuple[str, ...]:
    return FAILURE_TAG_EVIDENCE_KEYS.get(tag, ())


def group_failure_tags(tags: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for tag in tags:
        group = failure_tag_group(tag)
        grouped.setdefault(group, []).append(tag)
    for group, group_tags in grouped.items():
        grouped[group] = sorted(group_tags)
    return dict(sorted(grouped.items()))


def normalize_evidence(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: data[key] for key in keys if key in data}

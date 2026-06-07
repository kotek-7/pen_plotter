from __future__ import annotations

import json
import math
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

from character_dictionary.classification import (
    character_advance_ratio,
    character_display_scale,
    character_layout_offset,
    character_shape_variation_scale,
    classify_character,
    font_candidates_for_character,
)
from character_dictionary.hershey import HERSHEY_ASSET_PATH, load_hershey_asset
from character_dictionary.kanjivg import load_kanjivg_asset
from character_dictionary.models import CharacterTemplate, LaidOutStroke, LayoutConfig, StrokeTemplate
from character_dictionary.terminal import map_stroke_type_to_terminal

Stroke = npt.NDArray[np.float64]


class DictionaryLookupError(KeyError):
    pass


SCHEMA_VERSION = 1
DICTIONARY_ID = "kanjivg-backed-mvp"
KANJIVG_ASSET_PATH = Path(__file__).resolve().parent / "data" / "kanjivg_templates.json"


def _dedupe_character_order(chars: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for char in chars:
        if char in seen:
            continue
        seen.add(char)
        ordered.append(char)
    return tuple(ordered)


CORE_BUILTIN_CHARACTER_ORDER = ("永", "あ", "い", "う", "え", "お")
HIRAGANA_OUTLINE_CHARACTER_ORDER = tuple(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめも"
    "やゆよらりるれろわゐゑをん"
    "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
    "ぁぃぅぇぉゃゅょっゎゔ"
)
KATAKANA_OUTLINE_CHARACTER_ORDER = tuple(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモ"
    "ヤユヨラリルレロワヰヱヲン"
    "ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ"
    "ァィゥェォャュョッヮヴ"
)
EXTENDED_FONT_OUTLINE_CHARACTER_ORDER = (
    "今",
    "日",
    "本",
    "天",
    "気",
    "春",
    "川",
    "歩",
    "文",
    "字",
    "列",
    "質",
    "評",
    "価",
    "少",
    "長",
    "余",
    "白",
    "確",
    "認",
    "観",
    "察",
    "重",
    "要",
    "続",
    "複",
    "数",
    "行",
    "改",
    "同",
    "差",
    "変",
    "動",
    "速",
    "違",
    "終",
    "筆",
    "手",
    "持",
    "用",
    "意",
    "読",
    "見",
    "補",
    "候",
    "人",
    "一",
    "冗",
    "分",
    "十",
    "取",
    "含",
    "品",
    "器",
    "度",
    "整",
    "書",
    "比",
    "然",
    "章",
    "自",
    "較",
    "間",
)
EXTENDED_PUNCTUATION_ORDER = (
    "、",
    "。",
    "，",
    "．",
    "！",
    "？",
    "「",
    "」",
    "『",
    "』",
    "・",
    "ー",
    "!",
    "?",
    ",",
    ".",
    ":",
    ";",
    "-",
    "/",
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
)
ASCII_DIGIT_CHARACTER_ORDER = tuple("0123456789")
ASCII_UPPERCASE_CHARACTER_ORDER = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ASCII_LOWERCASE_CHARACTER_ORDER = tuple("abcdefghijklmnopqrstuvwxyz")
BUILTIN_CHARACTER_ORDER = _dedupe_character_order(
    CORE_BUILTIN_CHARACTER_ORDER
    + HIRAGANA_OUTLINE_CHARACTER_ORDER
    + KATAKANA_OUTLINE_CHARACTER_ORDER
    + EXTENDED_FONT_OUTLINE_CHARACTER_ORDER
    + EXTENDED_PUNCTUATION_ORDER
    + ASCII_DIGIT_CHARACTER_ORDER
    + ASCII_UPPERCASE_CHARACTER_ORDER
    + ASCII_LOWERCASE_CHARACTER_ORDER
)
BUILTIN_CHARACTERS = frozenset(BUILTIN_CHARACTER_ORDER)


def get_template(literal: str) -> CharacterTemplate:
    try:
        return _TEMPLATES[literal]
    except KeyError as exc:
        raise DictionaryLookupError(literal) from exc


def iter_builtin_templates() -> tuple[CharacterTemplate, ...]:
    return tuple(get_template(literal) for literal in BUILTIN_CHARACTER_ORDER)


def export_dictionary() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dictionary_id": DICTIONARY_ID,
        "character_count": len(BUILTIN_CHARACTER_ORDER),
        "characters": [template.to_dict() for template in iter_builtin_templates()],
    }


def export_dictionary_json(indent: int = 2) -> str:
    return json.dumps(export_dictionary(), ensure_ascii=False, indent=indent, sort_keys=True) + "\n"


def layout_text(text: str, config: LayoutConfig | None = None) -> list[LaidOutStroke]:
    cfg = config or LayoutConfig()
    if cfg.fit_to_page:
        cfg = _fit_layout_to_page(text, cfg)
    x = cfg.margin_left
    baseline_top = cfg.paper_height - cfg.margin_top
    y_top = baseline_top
    line_index = 0
    line_char_index = 0
    line_offsets = _line_offsets(cfg, line_index)
    strokes: list[LaidOutStroke] = []
    visible_counts: dict[str, int] = {}

    char_index = 0
    for char in text:
        if char == "\n":
            x = cfg.margin_left
            line_index += 1
            line_char_index = 0
            y_top = baseline_top - line_index * (
                cfg.char_size * cfg.line_height + cfg.baseline_drift_mm
            )
            line_offsets = _line_offsets(cfg, line_index)
            continue
        if char.isspace():
            x += cfg.char_size * (0.48 + 0.04 * cfg.layout_variation)
            line_char_index += 1
            continue

        repeat_index = visible_counts.get(char, 0)
        visible_counts[char] = repeat_index + 1
        layout_offset_x, layout_offset_y, advance_offset = _layout_offsets(
            char,
            char_index=char_index,
            config=cfg,
        )
        line_offset_x, line_offset_y, spacing_scale = line_offsets
        line_wave = math.sin((line_char_index + 1) * 0.7 + line_index * 0.45)
        template = _TEMPLATES.get(char)
        display_scale = template.display_scale if template is not None else character_display_scale(char)
        advance_ratio = template.advance_ratio if template is not None else character_advance_ratio(char)
        layout_shift_x, layout_shift_y = character_layout_offset(
            char,
            script_group=template.script_group if template is not None else None,
        )
        if template is None:
            stroke_entries = [
                (glyph_stroke, "none", "outline", index + 1)
                for index, glyph_stroke in enumerate(_fallback_glyph_strokes(char))
            ]
        else:
            stroke_entries = [
                (stroke.skeleton_points, stroke.terminal, stroke.stroke_type, stroke.order)
                for stroke in template.strokes
            ]

        for base_points, terminal, stroke_type, order in stroke_entries:
            if template is None:
                skeleton_points = base_points
            else:
                skeleton_points = _vary_skeleton_points(
                    char,
                    char_index=char_index,
                    stroke=StrokeTemplate(
                        stroke_id=order,
                        order=order,
                        stroke_type=stroke_type,
                        skeleton_points=base_points,
                        terminal=terminal,
                    ),
                    config=cfg,
                )
            skeleton_points = _scale_unit_points(skeleton_points, display_scale)
            points = tuple(
                (
                    x
                    + layout_offset_x
                    + line_offset_x * line_char_index
                    + line_wave * cfg.char_size * 0.02
                    + px * cfg.char_size
                    + layout_shift_x * cfg.char_size
                    + _slant_offset(py, cfg),
                    y_top
                    + layout_offset_y
                    + line_offset_y * line_char_index
                    + line_wave * cfg.char_size * 0.03
                    + repeat_index * cfg.layout_variation * cfg.char_size * 0.04
                    + layout_shift_y * cfg.char_size
                    - py * cfg.char_size,
                )
                for px, py in skeleton_points
            )
            strokes.append(
                LaidOutStroke(
                    points=points,
                    terminal=terminal,
                    literal=char,
                    stroke_type=stroke_type,
                    order=order,
                    char_index=char_index,
                    line_index=line_index,
                    line_char_index=line_char_index,
                    repeat_index=repeat_index,
                )
            )
        spacing_adjustment = cfg.char_spacing + advance_offset
        spacing_adjustment *= 1.0 + spacing_scale
        spacing_adjustment += min(repeat_index, 3) * cfg.layout_variation * cfg.char_size * 0.02
        if char in "、。，．,.!?！？":
            spacing_adjustment *= 0.72
        x += cfg.char_size * advance_ratio + spacing_adjustment
        char_index += 1
        line_char_index += 1
    return strokes


def _fit_layout_to_page(text: str, config: LayoutConfig) -> LayoutConfig:
    visible_lines = text.splitlines() or [text]
    usable_width = max(config.paper_width - config.margin_left * 2.0, config.char_size)
    usable_height = max(config.paper_height - config.margin_top * 2.0, config.char_size)

    estimated_line_widths = [_estimate_line_width(line, config) for line in visible_lines]
    widest_line = max(estimated_line_widths, default=0.0)
    line_step = config.char_size * config.line_height + config.baseline_drift_mm
    estimated_height = (
        config.char_size if len(visible_lines) <= 1 else config.char_size + (len(visible_lines) - 1) * line_step
    )

    width_scale = usable_width / widest_line if widest_line > 0.0 else 1.0
    height_scale = usable_height / estimated_height if estimated_height > 0.0 else 1.0
    scale = min(1.0, width_scale, height_scale)
    if scale >= 1.0:
        return config

    return replace(
        config,
        char_size=config.char_size * scale,
        char_spacing=config.char_spacing * scale,
        line_height=config.line_height * scale,
        baseline_drift_mm=config.baseline_drift_mm * scale,
    )


def _estimate_line_width(line: str, config: LayoutConfig) -> float:
    width = 0.0
    for char in line:
        if char.isspace():
            width += config.char_size * 0.48
            continue
        template = _TEMPLATES.get(char)
        advance_ratio = (
            template.advance_ratio if template is not None else character_advance_ratio(char)
        )
        width += config.char_size * advance_ratio + config.char_spacing
    if width > 0.0:
        width -= config.char_spacing
    return max(width, 0.0)


def _stroke(stroke_id: int, stroke_type: str, points: tuple[tuple[float, float], ...]) -> StrokeTemplate:
    return StrokeTemplate(
        stroke_id=stroke_id,
        order=stroke_id,
        stroke_type=stroke_type,
        skeleton_points=points,
        terminal=map_stroke_type_to_terminal(stroke_type),
    )


def _template(literal: str, strokes: tuple[StrokeTemplate, ...]) -> CharacterTemplate:
    script_group = classify_character(literal)
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source="manual-kanjivg-mvp",
        license="research-internal",
        bbox=(0.0, 0.0, 1.0, 1.0),
        strokes=strokes,
        script_group=script_group,
        display_scale=character_display_scale(literal, script_group=script_group, source="manual"),
        advance_ratio=character_advance_ratio(literal, script_group=script_group, source="manual"),
    )


def _font_outline_template(literal: str) -> CharacterTemplate:
    script_group = classify_character(literal)
    strokes = _font_outline_points(literal)
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source="font-outline",
        license="research-internal",
        bbox=(0.0, 0.0, 1.0, 1.0),
        strokes=tuple(
            _stroke(index + 1, "outline", points)
            for index, points in enumerate(strokes)
        ),
        script_group=script_group,
        display_scale=character_display_scale(
            literal,
            script_group=script_group,
            source="font-outline",
        ),
        advance_ratio=character_advance_ratio(
            literal,
            script_group=script_group,
            source="font-outline",
        ),
    )


def _vary_skeleton_points(
    literal: str,
    *,
    char_index: int,
    stroke: StrokeTemplate,
    config: LayoutConfig,
) -> tuple[tuple[float, float], ...]:
    script_group = classify_character(literal)
    strength = max(float(config.shape_variation), 0.0) * character_shape_variation_scale(
        literal,
        script_group=script_group,
    )
    if strength == 0.0:
        return stroke.skeleton_points

    rng = random.Random(
        f"{config.variation_seed}:{literal}:{char_index}:{stroke.stroke_id}:{stroke.stroke_type}"
    )
    slant = rng.uniform(-0.12, 0.12) * strength
    stretch_x = 1.0 + rng.uniform(-0.12, 0.12) * strength
    stretch_y = 1.0 + rng.uniform(-0.10, 0.10) * strength
    shift_x = rng.uniform(-0.12, 0.12) * strength
    shift_y = rng.uniform(-0.12, 0.12) * strength
    point_jitter = 0.12 * strength

    varied: list[tuple[float, float]] = []
    for index, (px, py) in enumerate(stroke.skeleton_points):
        endpoint_scale = 0.30 if index in {0, len(stroke.skeleton_points) - 1} else 1.0
        jitter_x = rng.uniform(-point_jitter, point_jitter) * endpoint_scale
        jitter_y = rng.uniform(-point_jitter, point_jitter) * endpoint_scale
        centered_x = (px - 0.5) * stretch_x + slant * (py - 0.5)
        centered_y = (py - 0.5) * stretch_y
        varied.append(
            (
                _clamp_unit(0.5 + centered_x + shift_x + jitter_x),
                _clamp_unit(0.5 + centered_y + shift_y + jitter_y),
            )
        )
    return tuple(varied)


def _layout_offsets(
    literal: str,
    *,
    char_index: int,
    config: LayoutConfig,
) -> tuple[float, float, float]:
    strength = max(float(config.layout_variation), 0.0)
    if strength == 0.0:
        return (0.0, 0.0, 0.0)

    rng = random.Random(f"{config.variation_seed}:{literal}:{char_index}:layout")
    offset_x = rng.uniform(-0.35, 0.35) * strength * config.char_size
    offset_y = rng.uniform(-0.40, 0.40) * strength * config.char_size
    advance_offset = rng.uniform(-0.45, 0.45) * strength * config.char_size
    return (offset_x, offset_y, advance_offset)


def _line_offsets(config: LayoutConfig, line_index: int) -> tuple[float, float, float]:
    strength = max(float(config.layout_variation), 0.0)
    if strength == 0.0:
        return (0.0, 0.0, 0.0)

    rng = random.Random(f"{config.variation_seed}:{line_index}:line")
    offset_x = rng.uniform(-0.06, 0.06) * strength * config.char_size
    offset_y = rng.uniform(-0.05, 0.05) * strength * config.char_size
    spacing_scale = rng.uniform(-0.12, 0.12) * strength
    return (offset_x, offset_y, spacing_scale)


def _fallback_glyph_strokes(char: str) -> list[Stroke]:
    return [np.array(points, dtype=float) for points in _font_outline_points(char)]


def _find_font(name: str | None, path: str | None, *, literal: str | None = None) -> FontProperties:
    group = classify_character(literal or "あ")
    weight = "bold" if group in {"latin", "digit", "punctuation", "symbol"} else "regular"
    if path is not None:
        return FontProperties(fname=path, weight=weight)
    if name:
        return FontProperties(family=name, weight=weight)

    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in font_candidates_for_character(literal or "あ"):
        if candidate in available:
            return FontProperties(family=candidate, weight=weight)
    return FontProperties(family="DejaVu Sans", weight=weight)


def _flatten_text_path(path: TextPath) -> list[Stroke]:
    strokes: list[Stroke] = []
    current: list[tuple[float, float]] = []

    for vertices, code in path.iter_segments(curves=False, simplify=False):
        if code == MplPath.MOVETO:
            if len(current) >= 2:
                strokes.append(np.array(current, dtype=float))
            current = [(float(vertices[0]), float(vertices[1]))]
        elif code == MplPath.LINETO:
            current.append((float(vertices[0]), float(vertices[1])))
        elif code == MplPath.CLOSEPOLY:
            if len(current) >= 2:
                current.append(current[0])
                strokes.append(np.array(current, dtype=float))
            current = []

    if len(current) >= 2:
        strokes.append(np.array(current, dtype=float))
    return strokes


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.04), 0.96)


def _font_outline_points(char: str) -> list[tuple[tuple[float, float], ...]]:
    font = _find_font(None, None, literal=char)
    char_path = TextPath((0, 0), char, size=1.0, prop=font)
    strokes = _flatten_text_path(char_path)
    return _normalize_strokes_to_unit_square(strokes)


def _normalize_strokes_to_unit_square(strokes: list[Stroke]) -> list[tuple[tuple[float, float], ...]]:
    if not strokes:
        return []

    all_points = np.concatenate(strokes, axis=0)
    min_x = float(np.min(all_points[:, 0]))
    max_x = float(np.max(all_points[:, 0]))
    min_y = float(np.min(all_points[:, 1]))
    max_y = float(np.max(all_points[:, 1]))
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    size = max(width, height, 1e-9)
    offset_x = (size - width) / 2.0
    offset_y = (size - height) / 2.0

    normalized: list[tuple[tuple[float, float], ...]] = []
    for stroke in strokes:
        normalized.append(
            tuple(
                (
                    _clamp_unit((float(x) - min_x + offset_x) / size),
                    _clamp_unit((float(y) - min_y + offset_y) / size),
                )
                for x, y in stroke
            )
        )
    return normalized


def _scale_unit_points(
    points: tuple[tuple[float, float], ...],
    scale: float,
) -> tuple[tuple[float, float], ...]:
    if scale == 1.0:
        return points
    return tuple(
        (
            _clamp_unit(0.5 + (x - 0.5) * scale),
            _clamp_unit(0.5 + (y - 0.5) * scale),
        )
        for x, y in points
    )


def _slant_offset(py: float, config: LayoutConfig) -> float:
    if config.slant_deg == 0.0:
        return 0.0
    return math.tan(math.radians(config.slant_deg)) * (py - 0.5) * config.char_size


def _build_templates() -> dict[str, CharacterTemplate]:
    kanjivg_templates = load_kanjivg_asset(KANJIVG_ASSET_PATH)
    hershey_templates = load_hershey_asset(HERSHEY_ASSET_PATH)
    templates: dict[str, CharacterTemplate] = {
        literal: template for literal, template in kanjivg_templates.items()
    }
    for literal in BUILTIN_CHARACTER_ORDER:
        if literal in templates:
            continue
        if literal == "永":
            templates[literal] = _template(
                "永",
                (
                    _stroke(1, "ten", ((0.50, 0.08), (0.54, 0.20))),
                    _stroke(2, "yoko", ((0.28, 0.30), (0.74, 0.30))),
                    _stroke(3, "tate", ((0.50, 0.22), (0.50, 0.78), (0.42, 0.94))),
                    _stroke(4, "hidari", ((0.44, 0.52), (0.30, 0.72), (0.16, 0.88))),
                    _stroke(5, "migi", ((0.56, 0.52), (0.70, 0.74), (0.86, 0.90))),
                ),
            )
            continue
        if literal in hershey_templates:
            templates[literal] = hershey_templates[literal]
            continue
        templates[literal] = _font_outline_template(literal)
    return templates


_TEMPLATES: dict[str, CharacterTemplate] = _build_templates()

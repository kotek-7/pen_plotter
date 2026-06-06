from __future__ import annotations

import json
import math
import random
from typing import Any

import numpy as np
import numpy.typing as npt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

from character_dictionary.models import CharacterTemplate, LaidOutStroke, LayoutConfig, StrokeTemplate
from character_dictionary.terminal import map_stroke_type_to_terminal

Stroke = npt.NDArray[np.float64]
PT_TO_MM = 25.4 / 72.0

DEFAULT_FONT_CANDIDATES = (
    "Noto Sans CJK JP",
    "Noto Serif CJK JP",
    "IPAexGothic",
    "IPAGothic",
    "Yu Gothic",
    "Meiryo",
    "TakaoGothic",
    "DejaVu Sans",
)


class DictionaryLookupError(KeyError):
    pass


SCHEMA_VERSION = 1
DICTIONARY_ID = "manual-kanjivg-mvp"
BUILTIN_CHARACTER_ORDER = ("永", "あ", "い", "う", "え", "お")
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
            points = tuple(
                (
                    x
                    + layout_offset_x
                    + line_offset_x * line_char_index
                    + line_wave * cfg.char_size * 0.02
                    + px * cfg.char_size
                    + _slant_offset(py, cfg),
                    y_top
                    + layout_offset_y
                    + line_offset_y * line_char_index
                    + line_wave * cfg.char_size * 0.03
                    + repeat_index * cfg.layout_variation * cfg.char_size * 0.04
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
        x += cfg.char_size + spacing_adjustment
        char_index += 1
        line_char_index += 1
    return strokes


def _stroke(stroke_id: int, stroke_type: str, points: tuple[tuple[float, float], ...]) -> StrokeTemplate:
    return StrokeTemplate(
        stroke_id=stroke_id,
        order=stroke_id,
        stroke_type=stroke_type,
        skeleton_points=points,
        terminal=map_stroke_type_to_terminal(stroke_type),
    )


def _template(literal: str, strokes: tuple[StrokeTemplate, ...]) -> CharacterTemplate:
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source="manual-kanjivg-mvp",
        license="research-internal",
        bbox=(0.0, 0.0, 1.0, 1.0),
        strokes=strokes,
    )


def _vary_skeleton_points(
    literal: str,
    *,
    char_index: int,
    stroke: StrokeTemplate,
    config: LayoutConfig,
) -> tuple[tuple[float, float], ...]:
    strength = max(float(config.shape_variation), 0.0)
    if strength == 0.0:
        return stroke.skeleton_points

    rng = random.Random(
        f"{config.variation_seed}:{literal}:{char_index}:{stroke.stroke_id}:{stroke.stroke_type}"
    )
    slant = rng.uniform(-0.25, 0.25) * strength
    stretch_x = 1.0 + rng.uniform(-0.35, 0.35) * strength
    stretch_y = 1.0 + rng.uniform(-0.30, 0.30) * strength
    shift_x = rng.uniform(-0.35, 0.35) * strength
    shift_y = rng.uniform(-0.35, 0.35) * strength
    point_jitter = 0.35 * strength

    varied: list[tuple[float, float]] = []
    for index, (px, py) in enumerate(stroke.skeleton_points):
        endpoint_scale = 0.45 if index in {0, len(stroke.skeleton_points) - 1} else 1.0
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
    font = _find_font(None, None)
    char_path = TextPath((0, 0), char, size=1.0, prop=font)
    return [stroke * PT_TO_MM for stroke in _flatten_text_path(char_path)]


def _find_font(name: str | None, path: str | None) -> FontProperties:
    if path is not None:
        return FontProperties(fname=path)
    if name:
        return FontProperties(family=name)

    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in DEFAULT_FONT_CANDIDATES:
        if candidate in available:
            return FontProperties(family=candidate)
    return FontProperties(family="DejaVu Sans")


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


def _slant_offset(py: float, config: LayoutConfig) -> float:
    if config.slant_deg == 0.0:
        return 0.0
    return math.tan(math.radians(config.slant_deg)) * (py - 0.5) * config.char_size


_TEMPLATES: dict[str, CharacterTemplate] = {
    "永": _template(
        "永",
        (
            _stroke(1, "ten", ((0.50, 0.08), (0.54, 0.20))),
            _stroke(2, "yoko", ((0.28, 0.30), (0.74, 0.30))),
            _stroke(3, "tate", ((0.50, 0.22), (0.50, 0.78), (0.42, 0.94))),
            _stroke(4, "hidari", ((0.44, 0.52), (0.30, 0.72), (0.16, 0.88))),
            _stroke(5, "migi", ((0.56, 0.52), (0.70, 0.74), (0.86, 0.90))),
        ),
    ),
    "あ": _template(
        "あ",
        (
            _stroke(1, "yoko", ((0.28, 0.28), (0.76, 0.28))),
            _stroke(2, "tate", ((0.50, 0.14), (0.48, 0.54))),
            _stroke(3, "migi", ((0.34, 0.54), (0.30, 0.82), (0.58, 0.90), (0.82, 0.66), (0.66, 0.48))),
        ),
    ),
    "い": _template(
        "い",
        (
            _stroke(1, "hidari", ((0.42, 0.22), (0.34, 0.48), (0.30, 0.72), (0.36, 0.90))),
            _stroke(2, "hane", ((0.66, 0.24), (0.72, 0.50), (0.68, 0.72), (0.60, 0.84))),
        ),
    ),
    "う": _template(
        "う",
        (
            _stroke(1, "ten", ((0.46, 0.18), (0.58, 0.22))),
            _stroke(2, "hidari", ((0.30, 0.42), (0.66, 0.38), (0.74, 0.62), (0.42, 0.86))),
        ),
    ),
    "え": _template(
        "え",
        (
            _stroke(1, "ten", ((0.46, 0.16), (0.58, 0.22))),
            _stroke(2, "yoko", ((0.30, 0.38), (0.70, 0.38))),
            _stroke(3, "migi", ((0.54, 0.40), (0.34, 0.68), (0.52, 0.64), (0.76, 0.86))),
        ),
    ),
    "お": _template(
        "お",
        (
            _stroke(1, "yoko", ((0.26, 0.28), (0.72, 0.28))),
            _stroke(2, "tate", ((0.48, 0.14), (0.48, 0.76))),
            _stroke(3, "migi", ((0.36, 0.58), (0.22, 0.82), (0.52, 0.88), (0.72, 0.66), (0.54, 0.50))),
            _stroke(4, "ten", ((0.74, 0.38), (0.84, 0.44))),
        ),
    ),
}

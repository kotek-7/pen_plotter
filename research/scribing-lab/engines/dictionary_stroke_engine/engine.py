from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENGINE_ID = "dictionary-stroke-engine"


@dataclass(frozen=True)
class EngineConfig:
    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_size: float = 12.0
    char_spacing: float = 2.5
    line_height: float = 1.45
    kana_scale: float = 1.0
    latin_scale: float = 0.62
    draw_speed_mm_s: float = 32.0
    penup_speed_mm_s: float = 110.0


@dataclass(frozen=True)
class StrokeTemplate:
    stroke_id: int
    order: int
    stroke_type: str
    skeleton_points: tuple[tuple[float, float], ...]
    terminal: str
    confidence: float = 1.0


@dataclass(frozen=True)
class CharacterTemplate:
    char_id: str
    literal: str
    source: str
    license: str
    bbox: tuple[float, float, float, float]
    strokes: tuple[StrokeTemplate, ...]
    script_group: str = "unknown"
    advance_ratio: float = 1.0
    display_scale: float = 1.0
    baseline_y: float | None = None


@dataclass(frozen=True)
class PositionedStroke:
    points: tuple[tuple[float, float], ...]
    stroke_type: str
    terminal: str
    char: str
    order: int


def generate(request: dict[str, Any]) -> dict[str, Any]:
    text = _normalize_text(str(request.get("text", "")))
    seed = int(request.get("seed", 1))
    params = dict(request.get("params", {}))
    config = _config_from_params(params)

    strokes, used_templates = _layout_text(text, config=config)
    trajectory = _strokes_to_trajectory(strokes, config=config)

    return {
        "engine_id": ENGINE_ID,
        "engine_parameters": {
            "seed": seed,
            "config": config.__dict__,
            "params": params,
            "dictionary": {
                "sources": _dictionary_sources(),
                "template_count": len(_DICTIONARY),
                "used_chars": sorted(used_templates),
                "fallback": "ascii-frame-or-missing-box",
            },
        },
        "trajectory": trajectory,
    }


def _config_from_params(params: dict[str, Any]) -> EngineConfig:
    values = EngineConfig().__dict__.copy()
    for key, raw in params.items():
        if key not in values:
            continue
        values[key] = float(raw)
    return EngineConfig(**values)


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _layout_text(
    text: str,
    *,
    config: EngineConfig,
) -> tuple[list[PositionedStroke], set[str]]:
    strokes: list[PositionedStroke] = []
    used_templates: set[str] = set()
    x = config.margin_left
    y_top = config.paper_height - config.margin_top
    line_advance = config.char_size * config.line_height
    max_x = config.paper_width - config.margin_left

    for char in text:
        if char == "\n":
            x = config.margin_left
            y_top -= line_advance
            continue
        if char.isspace():
            x += config.char_size * 0.55
            continue
        if x + config.char_size > max_x:
            x = config.margin_left
            y_top -= line_advance

        template = _template_for(char)
        used_templates.add(template.literal)
        char_size = config.char_size * _template_scale(template, config)
        draw_size = char_size * template.display_scale
        strokes.extend(
            _position_template(
                template,
                x=x,
                y_top=y_top,
                em_size=config.char_size,
                nominal_size=char_size,
                draw_size=draw_size,
            )
        )
        x += char_size * template.advance_ratio + config.char_spacing

    return strokes, used_templates


def _position_template(
    template: CharacterTemplate,
    *,
    x: float,
    y_top: float,
    em_size: float,
    nominal_size: float,
    draw_size: float,
) -> list[PositionedStroke]:
    """Place a template's normalized strokes onto the paper.

    Latin glyphs (``baseline_y`` set) keep their baseline fixed regardless of
    ``draw_size``. Full-width glyphs (``baseline_y`` is ``None``) are scaled about
    the shared em-box center so that kana, small kana, the long-vowel mark and
    punctuation stay vertically aligned with kanji (the KanjiVG em-box) instead of
    being top-anchored.
    """
    if template.baseline_y is not None:
        origin_y = (y_top - template.baseline_y * nominal_size) + template.baseline_y * draw_size

        def map_y(ny: float) -> float:
            return origin_y - ny * draw_size
    else:
        cell_center_y = y_top - em_size / 2.0

        def map_y(ny: float) -> float:
            return cell_center_y + (0.5 - ny) * draw_size

    positioned: list[PositionedStroke] = []
    for stroke in sorted(template.strokes, key=lambda item: item.order):
        points = tuple((x + nx * draw_size, map_y(ny)) for nx, ny in stroke.skeleton_points)
        positioned.append(
            PositionedStroke(
                points=points,
                stroke_type=stroke.stroke_type,
                terminal=stroke.terminal,
                char=template.literal,
                order=stroke.order,
            )
        )
    return positioned


def _strokes_to_trajectory(
    strokes: list[PositionedStroke],
    *,
    config: EngineConfig,
) -> list[dict[str, float | int]]:
    t_ms = 0.0
    current = (0.0, config.paper_height)
    out: list[dict[str, float | int]] = [_point(current, t_ms, pen_state=0, pressure=0.0)]

    for stroke in strokes:
        points = stroke.points
        if len(points) < 2:
            continue
        start = points[0]

        t_ms += _duration_ms(_distance(current, start), config.penup_speed_mm_s)
        out.append(_point(start, t_ms, pen_state=0, pressure=0.0))
        out.append(_point(start, t_ms, pen_state=1, pressure=1.0))

        for prev, point in zip(points, points[1:], strict=False):
            t_ms += _duration_ms(_distance(prev, point), config.draw_speed_mm_s)
            out.append(_point(point, t_ms, pen_state=1, pressure=1.0))

        end = points[-1]
        out.append(_point(end, t_ms, pen_state=0, pressure=0.0))
        current = end

    return out


def _point(point: tuple[float, float], t_ms: float, *, pen_state: int, pressure: float) -> dict[str, float | int]:
    return {
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        "t": int(round(t_ms)),
        "pen_state": pen_state,
        "pressure": round(max(0.0, min(1.0, pressure)), 4),
    }


def _duration_ms(distance_mm: float, speed_mm_s: float) -> float:
    if speed_mm_s <= 0:
        raise ValueError("speed_mm_s must be positive")
    return distance_mm / speed_mm_s * 1000.0


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _template_for(char: str) -> CharacterTemplate:
    if char in _DICTIONARY:
        return _DICTIONARY[char]
    if char in _SYMBOL_TEMPLATES:
        return _SYMBOL_TEMPLATES[char]
    if char.isascii() and char.isprintable():
        return _ASCII_FALLBACK
    return _MISSING_FALLBACK


def _template_scale(template: CharacterTemplate, config: EngineConfig) -> float:
    if template.script_group in {"hiragana", "katakana"}:
        return config.kana_scale
    if template.script_group in {"latin", "digit"}:
        return config.latin_scale
    return 1.0


def _load_template_dictionary(filename: str, *, default_source: str, default_license: str) -> dict[str, CharacterTemplate]:
    path = Path(__file__).with_name("data") / filename
    raw = json.loads(path.read_text(encoding="utf-8"))
    _ASSET_METADATA[filename] = {
        "source": str(raw.get("source", default_source)),
        "license": str(raw.get("license", default_license)),
        "release": str(raw.get("release", "")),
        "source_url": str(raw.get("source_url", "")),
        "character_count": int(raw.get("character_count", len(raw.get("characters", [])))),
    }
    templates: dict[str, CharacterTemplate] = {}
    for item in raw["characters"]:
        literal = str(item["literal"])
        strokes = tuple(
            StrokeTemplate(
                stroke_id=int(stroke["stroke_id"]),
                order=int(stroke["order"]),
                stroke_type=_normalize_stroke_type(str(stroke.get("stroke_type", "none"))),
                skeleton_points=tuple((float(x), float(y)) for x, y in stroke["skeleton_points"]),
                terminal=str(stroke.get("terminal", "none")),
                confidence=float(stroke.get("confidence", 1.0)),
            )
            for stroke in item["strokes"]
        )
        templates[literal] = CharacterTemplate(
            char_id=str(item["char_id"]),
            literal=literal,
            source=str(item.get("source", default_source)),
            license=str(item.get("license", default_license)),
            bbox=tuple(float(value) for value in item.get("bbox", [0.0, 0.0, 1.0, 1.0])),
            strokes=strokes,
            script_group=str(item.get("script_group", _classify_script(literal))),
            advance_ratio=float(item.get("advance_ratio", 1.0)),
            display_scale=float(item.get("display_scale", 1.0)),
            baseline_y=_optional_float(item.get("baseline_y")),
        )
    return templates


def _normalize_stroke_type(value: str) -> str:
    first = value.split("/", maxsplit=1)[0]
    return {
        "㇔": "ten",
        "㇐": "yoko",
        "㇑": "tate",
        "㇒": "hidari",
        "㇏": "migi",
        "㇀": "hane",
        "㇆": "ori",
        "㇇": "ori",
        "line": "none",
        "none": "none",
    }.get(first, "none")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _classify_script(char: str) -> str:
    code = ord(char)
    if 0x3040 <= code <= 0x309F:
        return "hiragana"
    if 0x30A0 <= code <= 0x30FF:
        return "katakana"
    if "0" <= char <= "9":
        return "digit"
    if ("A" <= char <= "Z") or ("a" <= char <= "z"):
        return "latin"
    if char in _SYMBOL_CHARS:
        return "symbol"
    return "kanji"


def _dictionary_sources() -> list[dict[str, str]]:
    kanjivg = _ASSET_METADATA.get("kanjivg_templates.json", {})
    hershey = _ASSET_METADATA.get("hershey_templates.json", {})
    return [
        {key: str(value) for key, value in kanjivg.items() if value},
        {key: str(value) for key, value in hershey.items() if value},
        {"source": "hand-authored-symbols", "license": "project-local"},
    ]


def _stroke(
    stroke_id: int,
    stroke_type: str,
    terminal: str,
    points: tuple[tuple[float, float], ...],
) -> StrokeTemplate:
    return StrokeTemplate(
        stroke_id=stroke_id,
        order=stroke_id,
        stroke_type=stroke_type,
        skeleton_points=points,
        terminal=terminal,
    )


def _char(literal: str, strokes: tuple[StrokeTemplate, ...]) -> CharacterTemplate:
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source="hand-authored-mvp",
        license="project-local",
        bbox=(0.0, 0.0, 1.0, 1.0),
        strokes=strokes,
        script_group=_classify_script(literal),
    )


# hand-authored 記号は full em-box ([0,1]) 前提で書かれているため、この比率で
# em-box 中心に向けて縮小した値を template データへ内包する。レイアウト時の
# script スケールには依存せず、記号グリフは常にこのサイズで配置される。
_SYMBOL_GLYPH_SCALE = 0.45


def _symbol_template(literal: str, strokes: tuple[StrokeTemplate, ...], *, advance_ratio: float = 0.55) -> CharacterTemplate:
    s = _SYMBOL_GLYPH_SCALE
    scaled = tuple(
        StrokeTemplate(
            stroke_id=stroke.stroke_id,
            order=stroke.order,
            stroke_type=stroke.stroke_type,
            skeleton_points=tuple(
                (nx * s, 0.5 - 0.5 * s + ny * s) for nx, ny in stroke.skeleton_points
            ),
            terminal=stroke.terminal,
            confidence=stroke.confidence,
        )
        for stroke in strokes
    )
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source="hand-authored-symbols",
        license="project-local",
        bbox=(0.0, 0.0, 1.0, 1.0),
        strokes=scaled,
        script_group="symbol",
        advance_ratio=advance_ratio * s,
    )


_SYMBOL_CHARS = set(",.!?「」『』()[]+-=*/:;")

_SYMBOL_TEMPLATES: dict[str, CharacterTemplate] = {
    ".": _symbol_template(".", (_stroke(1, "ten", "tome", ((0.48, 0.80), (0.52, 0.84))),), advance_ratio=0.35),
    ",": _symbol_template(",", (_stroke(1, "ten", "harai", ((0.52, 0.74), (0.44, 0.92))),), advance_ratio=0.35),
    "!": _symbol_template("!", (_stroke(1, "tate", "tome", ((0.50, 0.18), (0.50, 0.62))), _stroke(2, "ten", "tome", ((0.50, 0.80), (0.50, 0.84)))), advance_ratio=0.4),
    "?": _symbol_template("?", (_stroke(1, "none", "none", ((0.34, 0.28), (0.48, 0.16), (0.66, 0.28), (0.58, 0.48), (0.50, 0.58))), _stroke(2, "ten", "tome", ((0.50, 0.80), (0.50, 0.84)))), advance_ratio=0.62),
    "-": _symbol_template("-", (_stroke(1, "yoko", "tome", ((0.24, 0.52), (0.76, 0.52))),), advance_ratio=0.58),
    "+": _symbol_template("+", (_stroke(1, "yoko", "tome", ((0.24, 0.50), (0.76, 0.50))), _stroke(2, "tate", "tome", ((0.50, 0.24), (0.50, 0.76)))), advance_ratio=0.62),
    "=": _symbol_template("=", (_stroke(1, "yoko", "tome", ((0.24, 0.42), (0.76, 0.42))), _stroke(2, "yoko", "tome", ((0.24, 0.62), (0.76, 0.62)))), advance_ratio=0.62),
    "*": _symbol_template("*", (_stroke(1, "none", "tome", ((0.50, 0.24), (0.50, 0.76))), _stroke(2, "none", "tome", ((0.27, 0.36), (0.73, 0.64))), _stroke(3, "none", "tome", ((0.73, 0.36), (0.27, 0.64)))), advance_ratio=0.62),
    "/": _symbol_template("/", (_stroke(1, "hidari", "harai", ((0.74, 0.18), (0.26, 0.84))),), advance_ratio=0.55),
    ":": _symbol_template(":", (_stroke(1, "ten", "tome", ((0.50, 0.38), (0.50, 0.42))), _stroke(2, "ten", "tome", ((0.50, 0.70), (0.50, 0.74)))), advance_ratio=0.35),
    ";": _symbol_template(";", (_stroke(1, "ten", "tome", ((0.50, 0.38), (0.50, 0.42))), _stroke(2, "ten", "harai", ((0.52, 0.70), (0.44, 0.90)))), advance_ratio=0.35),
    "「": _symbol_template("「", (_stroke(1, "ori", "tome", ((0.68, 0.20), (0.38, 0.20), (0.38, 0.50))),), advance_ratio=0.42),
    "」": _symbol_template("」", (_stroke(1, "ori", "tome", ((0.62, 0.50), (0.62, 0.80), (0.32, 0.80))),), advance_ratio=0.42),
    "『": _symbol_template("『", (_stroke(1, "ori", "tome", ((0.72, 0.16), (0.34, 0.16), (0.34, 0.56))), _stroke(2, "ori", "tome", ((0.58, 0.30), (0.44, 0.30), (0.44, 0.50)))), advance_ratio=0.5),
    "』": _symbol_template("』", (_stroke(1, "ori", "tome", ((0.66, 0.44), (0.66, 0.84), (0.28, 0.84))), _stroke(2, "ori", "tome", ((0.56, 0.50), (0.56, 0.70), (0.42, 0.70)))), advance_ratio=0.5),
    "(": _symbol_template("(", (_stroke(1, "none", "none", ((0.64, 0.16), (0.42, 0.34), (0.38, 0.66), (0.64, 0.84))),), advance_ratio=0.45),
    ")": _symbol_template(")", (_stroke(1, "none", "none", ((0.36, 0.16), (0.58, 0.34), (0.62, 0.66), (0.36, 0.84))),), advance_ratio=0.45),
    "[": _symbol_template("[", (_stroke(1, "ori", "tome", ((0.66, 0.18), (0.40, 0.18), (0.40, 0.82), (0.66, 0.82))),), advance_ratio=0.45),
    "]": _symbol_template("]", (_stroke(1, "ori", "tome", ((0.34, 0.18), (0.60, 0.18), (0.60, 0.82), (0.34, 0.82))),), advance_ratio=0.45),
}

_ASSET_METADATA: dict[str, dict[str, str | int]] = {}

_DICTIONARY: dict[str, CharacterTemplate] = {
    **_load_template_dictionary("kanjivg_templates.json", default_source="kanjivg", default_license="CC BY-SA 3.0"),
    **_load_template_dictionary("hershey_templates.json", default_source="hershey", default_license="Hershey Fonts"),
    **_SYMBOL_TEMPLATES,
}

_ASCII_FALLBACK = _char(
    "?",
    (
        _stroke(1, "yoko", "tome", ((0.22, 0.18), (0.78, 0.18))),
        _stroke(2, "tate", "tome", ((0.22, 0.18), (0.22, 0.80))),
        _stroke(3, "yoko", "tome", ((0.22, 0.80), (0.78, 0.80))),
        _stroke(4, "tate", "tome", ((0.78, 0.18), (0.78, 0.80))),
    ),
)

_MISSING_FALLBACK = _char(
    "□",
    (
        _stroke(1, "none", "none", ((0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.25, 0.25))),
    ),
)

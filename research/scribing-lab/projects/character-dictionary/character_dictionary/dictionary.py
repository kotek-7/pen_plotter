from __future__ import annotations

from character_dictionary.models import CharacterTemplate, LaidOutStroke, LayoutConfig, StrokeTemplate
from character_dictionary.terminal import map_stroke_type_to_terminal


class DictionaryLookupError(KeyError):
    pass


BUILTIN_CHARACTERS = frozenset({"永", "あ", "い", "う", "え", "お"})


def get_template(literal: str) -> CharacterTemplate:
    try:
        return _TEMPLATES[literal]
    except KeyError as exc:
        raise DictionaryLookupError(literal) from exc


def layout_text(text: str, config: LayoutConfig | None = None) -> list[LaidOutStroke]:
    cfg = config or LayoutConfig()
    x = cfg.margin_left
    baseline_top = cfg.paper_height - cfg.margin_top
    y_top = baseline_top
    strokes: list[LaidOutStroke] = []

    for char in text:
        if char == "\n":
            x = cfg.margin_left
            y_top -= cfg.char_size * cfg.line_height
            continue
        if char.isspace():
            x += cfg.char_size * 0.5
            continue

        template = get_template(char)
        for stroke in template.strokes:
            points = tuple((x + px * cfg.char_size, y_top - py * cfg.char_size) for px, py in stroke.skeleton_points)
            strokes.append(
                LaidOutStroke(
                    points=points,
                    terminal=stroke.terminal,
                    literal=char,
                    stroke_type=stroke.stroke_type,
                    order=stroke.order,
                )
            )
        x += cfg.char_size + cfg.char_spacing
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
            _stroke(1, "hidari", ((0.34, 0.24), (0.30, 0.52), (0.38, 0.78))),
            _stroke(2, "hane", ((0.66, 0.26), (0.72, 0.58), (0.66, 0.76))),
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

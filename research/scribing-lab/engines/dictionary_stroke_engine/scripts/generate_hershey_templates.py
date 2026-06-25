from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from HersheyFonts import HersheyFonts


HERSHEY_FONT_NAME = "futural"
HERSHEY_LICENSE = "Hershey Fonts"
HERSHEY_SOURCE = "hershey"
HERSHEY_METRICS = {
    "cap_top": -12.0,
    "x_height_top": -5.0,
    "baseline": 9.0,
    "descender": 16.0,
}
UNIT_METRICS = {
    "cap_top": 0.08,
    "x_height_top": 0.32,
    "baseline": 0.78,
    "descender": 0.96,
}
LITERALS = tuple(
    [*(chr(code) for code in range(ord("0"), ord("9") + 1))]
    + [*(chr(code) for code in range(ord("A"), ord("Z") + 1))]
    + [*(chr(code) for code in range(ord("a"), ord("z") + 1))]
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Hershey template asset for dictionary_stroke_engine.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "hershey_templates.json",
        help="Output JSON asset path.",
    )
    parser.add_argument("--font-name", default=HERSHEY_FONT_NAME, help="Built-in Hershey font name.")
    args = parser.parse_args()

    asset = build_hershey_asset(font_name=args.font_name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asset, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} ({asset['character_count']} characters)")


def build_hershey_asset(*, font_name: str) -> dict[str, object]:
    font = HersheyFonts()
    font.load_default_font(font_name)
    glyphs = {literal: next(font.glyphs_for_text(literal)) for literal in LITERALS}
    frame = _font_frame(glyphs)

    entries = [_template_entry(literal, glyphs[literal], frame=frame) for literal in LITERALS]
    return {
        "schema_version": 1,
        "source": HERSHEY_SOURCE,
        "license": HERSHEY_LICENSE,
        "font_name": font_name,
        "character_count": len(entries),
        "font_frame": [round(value, 6) for value in frame],
        "font_metrics": HERSHEY_METRICS,
        "unit_metrics": UNIT_METRICS,
        "characters": entries,
    }


def _template_entry(literal: str, glyph: object, *, frame: tuple[float, float, float, float]) -> dict[str, object]:
    raw_strokes = [tuple((float(x), float(y)) for x, y in stroke) for stroke in glyph.strokes]
    strokes = _normalize_strokes_to_font_frame(raw_strokes, frame)
    if not strokes:
        raise ValueError(f"no Hershey strokes found for {literal!r}")

    bbox = _bbox_from_strokes(strokes)
    width_scale = max(float(getattr(glyph, "char_width", 20.0)), 1.0) / 20.0
    display_scale = 0.92 if literal.isalpha() else 0.84
    advance_ratio = max(0.34, min(1.60, width_scale * 0.95))

    return {
        "advance_ratio": advance_ratio,
        "bbox": [round(value, 6) for value in bbox],
        "char_id": f"U+{ord(literal):04X}",
        "display_scale": display_scale,
        "license": HERSHEY_LICENSE,
        "literal": literal,
        "script_group": "latin" if literal.isalpha() else "digit",
        "source": HERSHEY_SOURCE,
        "strokes": [
            {
                "confidence": 1.0,
                "order": index + 1,
                "path": "",
                "skeleton_points": [[round(x, 6), round(y, 6)] for x, y in points],
                "stroke_id": index + 1,
                "stroke_type": "line",
                "terminal": "none",
            }
            for index, points in enumerate(strokes)
        ],
    }


def _font_frame(glyphs: dict[str, object]) -> tuple[float, float, float, float]:
    max_width = max(float(getattr(glyph, "char_width", 20.0)) for glyph in glyphs.values())
    return (-max_width / 2.0, HERSHEY_METRICS["cap_top"], max_width, HERSHEY_METRICS["descender"] - HERSHEY_METRICS["cap_top"])


def _normalize_strokes_to_font_frame(
    strokes: list[tuple[tuple[float, float], ...]],
    frame: tuple[float, float, float, float],
) -> list[tuple[tuple[float, float], ...]]:
    if not strokes:
        return []

    min_x, min_y, width, height = frame
    size = max(width, height, 1e-9)
    offset_x = (size - width) / 2.0
    return [
        tuple(
            (
                _clamp_unit((x - min_x + offset_x) / size),
                _clamp_unit(_normalize_y(y)),
            )
            for x, y in stroke
        )
        for stroke in strokes
    ]


def _normalize_y(y: float) -> float:
    if y <= HERSHEY_METRICS["x_height_top"]:
        return _map_range(
            y,
            HERSHEY_METRICS["cap_top"],
            HERSHEY_METRICS["x_height_top"],
            UNIT_METRICS["cap_top"],
            UNIT_METRICS["x_height_top"],
        )
    if y <= HERSHEY_METRICS["baseline"]:
        return _map_range(
            y,
            HERSHEY_METRICS["x_height_top"],
            HERSHEY_METRICS["baseline"],
            UNIT_METRICS["x_height_top"],
            UNIT_METRICS["baseline"],
        )
    return _map_range(
        y,
        HERSHEY_METRICS["baseline"],
        HERSHEY_METRICS["descender"],
        UNIT_METRICS["baseline"],
        UNIT_METRICS["descender"],
    )


def _map_range(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    return dst_min + (value - src_min) / (src_max - src_min) * (dst_max - dst_min)


def _bbox_from_strokes(strokes: list[tuple[tuple[float, float], ...]]) -> tuple[float, float, float, float]:
    xs = [x for stroke in strokes for x, _ in stroke]
    ys = [y for stroke in strokes for _, y in stroke]
    return (min(xs), min(ys), max(xs), max(ys))


def _clamp_unit(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("non-finite coordinate")
    return min(max(value, 0.04), 0.96)


if __name__ == "__main__":
    main()

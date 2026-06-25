from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from HersheyFonts import HersheyFonts


HERSHEY_FONT_NAME = "futural"
HERSHEY_LICENSE = "Hershey Fonts"
HERSHEY_SOURCE = "hershey"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "character_dictionary" / "data" / "hershey_templates.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Hershey template asset")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON asset path")
    parser.add_argument("--font-name", default=HERSHEY_FONT_NAME, help="Built-in Hershey font name")
    args = parser.parse_args()

    literals = [*(chr(code) for code in range(ord("0"), ord("9") + 1))]
    literals.extend(chr(code) for code in range(ord("A"), ord("Z") + 1))
    literals.extend(chr(code) for code in range(ord("a"), ord("z") + 1))
    dump_hershey_asset(Path(args.output), literals, font_name=args.font_name)
    print(f"wrote {args.output}")


def dump_hershey_asset(path: Path, literals: list[str] | tuple[str, ...], *, font_name: str) -> None:
    asset = build_hershey_asset(literals, font_name=font_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asset, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_hershey_asset(
    literals: list[str] | tuple[str, ...],
    *,
    font_name: str,
) -> dict[str, object]:
    font = HersheyFonts()
    font.load_default_font(font_name)

    entries: list[dict[str, object]] = []
    for literal in literals:
        try:
            template = build_hershey_template(font, literal)
        except Exception:
            continue
        entries.append(template)
    return {
        "schema_version": 1,
        "source": HERSHEY_SOURCE,
        "license": HERSHEY_LICENSE,
        "font_name": font_name,
        "character_count": len(entries),
        "characters": entries,
    }


def build_hershey_template(font: HersheyFonts, literal: str) -> dict[str, object]:
    glyph_iter = font.glyphs_for_text(literal)
    glyph = next(glyph_iter)
    raw_strokes = list(glyph.strokes)
    if not raw_strokes:
        raise ValueError(f"no Hershey strokes found for {literal!r}")

    strokes = _normalize_strokes_to_unit_square(
        [np.array(stroke, dtype=float) for stroke in raw_strokes]
    )
    if not strokes:
        raise ValueError(f"failed to normalize Hershey strokes for {literal!r}")

    width_scale = max(float(getattr(glyph, "char_width", 20)), 1.0) / 20.0
    display_scale = 0.92 if literal.isalpha() else 0.84
    if literal.isdigit():
        display_scale = 0.84
    advance_ratio = max(0.34, min(1.60, width_scale * 0.95))

    return {
        "char_id": f"U+{ord(literal):04X}",
        "literal": literal,
        "source": HERSHEY_SOURCE,
        "license": HERSHEY_LICENSE,
        "bbox": (0.0, 0.0, 1.0, 1.0),
        "strokes": tuple(
            {
                "stroke_id": index + 1,
                "order": index + 1,
                "stroke_type": "line",
                "skeleton_points": points,
                "terminal": "none",
                "path": "",
                "confidence": 1.0,
            }
            for index, points in enumerate(strokes)
        ),
        "script_group": "latin" if literal.isalpha() else "digit",
        "display_scale": display_scale,
        "advance_ratio": advance_ratio,
    }


def _normalize_strokes_to_unit_square(
    strokes: list[np.ndarray],
) -> list[tuple[tuple[float, float], ...]]:
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


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.04), 0.96)


if __name__ == "__main__":
    main()

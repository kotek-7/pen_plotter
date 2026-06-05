from __future__ import annotations

import argparse
from pathlib import Path

from src.gcode.config import PlotterConfig
from src.gcode.generator import GCodeGenerator
from src.gcode.optimizer import optimize_stroke_order
from src.gcode.preview import preview_strokes
from src.textplot import RenderConfig, render_text


def _read_text(args: argparse.Namespace) -> str:
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    raise SystemExit("--text or --text-file is required")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render plain text to xDraw A4 G-code.")
    parser.add_argument("--text", help="Text to render.")
    parser.add_argument("--text-file", help="UTF-8 text file to render.")
    parser.add_argument("-o", "--output", required=True, help="Output .gcode path.")
    parser.add_argument("--preview", help="Optional preview image path.")
    parser.add_argument("--font-name", help="Matplotlib font family name.")
    parser.add_argument("--font-path", type=Path, help="Path to a TrueType/OpenType font.")
    parser.add_argument("--font-size", type=float, default=7.0, help="Font size in mm.")
    parser.add_argument("--margin-left", type=float, default=12.0, help="Left margin in mm.")
    parser.add_argument("--margin-top", type=float, default=16.0, help="Top margin in mm.")
    parser.add_argument("--line-height", type=float, default=1.45, help="Line height multiplier.")
    parser.add_argument("--char-spacing", type=float, default=0.8, help="Extra spacing in mm.")
    parser.add_argument("--jitter", type=float, default=0.08, help="Random point jitter in mm.")
    parser.add_argument("--wobble", type=float, default=0.04, help="Smooth stroke wobble in mm.")
    parser.add_argument("--seed", type=int, default=1, help="Random seed.")
    parser.add_argument("--no-optimize", action="store_true", help="Keep original stroke order.")
    parser.add_argument("--no-vary-speed", action="store_true", help="Disable feed-rate variation.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    text = _read_text(args)
    render_config = RenderConfig(
        font_size=args.font_size,
        margin_left=args.margin_left,
        margin_top=args.margin_top,
        line_height=args.line_height,
        char_spacing=args.char_spacing,
        jitter=args.jitter,
        wobble=args.wobble,
        seed=args.seed,
        font_name=args.font_name,
        font_path=args.font_path,
    )

    strokes = render_text(text, render_config)
    if not args.no_optimize:
        strokes = optimize_stroke_order(strokes, start_pos=(0.0, render_config.paper_height))

    generator = GCodeGenerator(PlotterConfig())
    lines = generator.generate(strokes, vary_speed=not args.no_vary_speed)
    generator.save(lines, args.output)

    if args.preview:
        preview_strokes(strokes, save_path=args.preview)

    print(f"Saved {len(strokes)} strokes to {args.output}")


if __name__ == "__main__":
    main()

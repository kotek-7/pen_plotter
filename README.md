# Pen Plotter

Plain text to xDraw A4 G-code.

This app renders text with a local font, adds small deterministic stroke variation,
converts the result to A4 paper-coordinate strokes, and writes xDraw-compatible G-code.

## Install

```sh
uv sync --extra dev
```

## Generate G-code

```sh
python scripts/text_to_gcode.py --text "Hello" -o output.gcode --preview preview.png
```

For Japanese text, specify a font installed on your system if the default font does not
contain the glyphs.

```sh
python scripts/text_to_gcode.py \
  --text "こんにちは" \
  --font-name "Noto Sans CJK JP" \
  -o hello.gcode \
  --preview hello.png
```

Useful options:

- `--font-size`: character size in mm
- `--margin-left`, `--margin-top`: page margins in mm
- `--jitter`, `--wobble`: handwritten-style stroke variation
- `--seed`: deterministic variation seed
- `--font-name` or `--font-path`: font selection

## Send G-code

Run the sender on Windows native Python when using the xDraw A4 over USB.

```sh
python scripts/run_plotter_gui.py
```

or:

```sh
python -m src.plotter_gui
```

## Development

```sh
make test
make lint
make format
```

The generator uses A4 paper coordinates: `(0, 0)` is the bottom-left corner,
`(210, 297)` is the top-right corner, units are millimeters, and Y points upward.

## Research

Research toward human-like Japanese scribing is kept separate from this application under:

```text
research/scribing-lab/
```

That research project is independent from the application code in `src/`. It has its own
documents, experiment harness, and per-project plans. See
`research/scribing-lab/README.md`.

`docs/scribing_engine.md` is an entry point for the research project. The maintained
research documents are under `research/scribing-lab/docs/`.

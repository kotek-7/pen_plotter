# Dictionary Data

`kanjivg_templates.json` is a normalized full main-release asset derived from KanjiVG.

- Source: https://github.com/KanjiVG/kanjivg
- Release: r20250816
- Format reference: https://kanjivg.tagaini.net/svg-format.html
- License: CC BY-SA 3.0
- Regeneration:
  `python engines/dictionary_stroke_engine/scripts/generate_kanjivg_templates.py`

`hershey_templates.json` is a normalized ASCII stroke asset derived from Hershey Fonts.

- Source: Hershey Fonts
- License: Hershey Fonts
- Regeneration:
  `uv run --with Hershey-Fonts python engines/dictionary_stroke_engine/scripts/generate_hershey_templates.py`

The engine preserves source and license metadata in `engine_parameters.dictionary.sources`.

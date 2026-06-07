from __future__ import annotations

import json
from pathlib import Path

from character_dictionary.classification import classify_character
from character_dictionary.models import CharacterTemplate, StrokeTemplate


HERSHEY_ASSET_PATH = Path(__file__).resolve().parent / "data" / "hershey_templates.json"
HERSHEY_SOURCE = "hershey"


def load_hershey_asset(path: Path = HERSHEY_ASSET_PATH) -> dict[str, CharacterTemplate]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    templates: dict[str, CharacterTemplate] = {}
    for item in payload.get("characters", []):
        strokes = tuple(
            StrokeTemplate(
                stroke_id=int(stroke["stroke_id"]),
                order=int(stroke["order"]),
                stroke_type=str(stroke.get("stroke_type", "line")),
                skeleton_points=tuple((float(x), float(y)) for x, y in stroke["skeleton_points"]),
                terminal=str(stroke.get("terminal", "none")),
                path=str(stroke.get("path", "")),
                confidence=float(stroke.get("confidence", 1.0)),
            )
            for stroke in item.get("strokes", [])
        )
        literal = str(item["literal"])
        templates[literal] = CharacterTemplate(
            char_id=str(item["char_id"]),
            literal=literal,
            source=str(item.get("source", HERSHEY_SOURCE)),
            license=str(item.get("license", "")),
            bbox=tuple(float(value) for value in item.get("bbox", (0.0, 0.0, 1.0, 1.0))),
            strokes=strokes,
            script_group=str(item.get("script_group", classify_character(literal))),
            display_scale=float(item.get("display_scale", 1.0)),
            advance_ratio=float(item.get("advance_ratio", 1.0)),
        )
    return templates

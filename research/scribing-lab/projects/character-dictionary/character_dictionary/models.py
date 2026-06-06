from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


Point = tuple[float, float]


@dataclass(frozen=True)
class StrokeTemplate:
    stroke_id: int
    order: int
    stroke_type: str
    skeleton_points: tuple[Point, ...]
    terminal: str
    path: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["skeleton_points"] = [list(point) for point in self.skeleton_points]
        return data


@dataclass(frozen=True)
class CharacterTemplate:
    char_id: str
    literal: str
    source: str
    license: str
    bbox: tuple[float, float, float, float]
    strokes: tuple[StrokeTemplate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "literal": self.literal,
            "source": self.source,
            "license": self.license,
            "bbox": list(self.bbox),
            "strokes": [stroke.to_dict() for stroke in self.strokes],
        }


@dataclass(frozen=True)
class LayoutConfig:
    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_size: float = 9.0
    char_spacing: float = 1.0
    line_height: float = 1.45
    slant_deg: float = 0.0
    baseline_drift_mm: float = 0.0
    shape_variation: float = 0.0
    layout_variation: float = 0.0
    variation_seed: int = 0


@dataclass(frozen=True)
class LaidOutStroke:
    points: tuple[Point, ...]
    terminal: str
    literal: str
    stroke_type: str
    order: int
    char_index: int = 0
    line_index: int = 0
    line_char_index: int = 0
    repeat_index: int = 0

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


Point = tuple[float, float]


@dataclass(frozen=True)
class SkeletonStroke:
    points: tuple[Point, ...]
    terminal: str = "none"
    literal: str = ""
    stroke_type: str = "none"


@dataclass(frozen=True)
class MotionPoint:
    x: float
    y: float
    t: int
    pen_state: int
    pressure: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

Stroke = npt.NDArray[np.float64]

PT_TO_MM = 25.4 / 72.0
DEFAULT_FONT_CANDIDATES = (
    "Noto Sans CJK JP",
    "Noto Serif CJK JP",
    "IPAexGothic",
    "IPAGothic",
    "Yu Gothic",
    "Meiryo",
    "TakaoGothic",
    "DejaVu Sans",
)


@dataclass(frozen=True)
class RenderConfig:
    """Text rendering settings in paper millimeters."""

    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    font_size: float = 7.0
    line_height: float = 1.45
    char_spacing: float = 0.8
    max_width: float | None = None
    jitter: float = 0.08
    wobble: float = 0.04
    seed: int = 1
    samples_per_curve: int = 12
    font_name: str | None = None
    font_path: Path | None = None

    @property
    def content_width(self) -> float:
        return self.max_width or (self.paper_width - self.margin_left * 2)


def _find_font(name: str | None, path: Path | None) -> FontProperties:
    if path is not None:
        return FontProperties(fname=str(path))
    if name:
        return FontProperties(family=name)

    available = {f.name for f in font_manager.fontManager.ttflist}
    for candidate in DEFAULT_FONT_CANDIDATES:
        if candidate in available:
            return FontProperties(family=candidate)
    return FontProperties(family="DejaVu Sans")


def _flatten_text_path(path: TextPath) -> list[Stroke]:
    strokes: list[Stroke] = []
    current: list[tuple[float, float]] = []

    for vertices, code in path.iter_segments(curves=False, simplify=False):
        if code == MplPath.MOVETO:
            if len(current) >= 2:
                strokes.append(np.array(current, dtype=float))
            current = [(float(vertices[0]), float(vertices[1]))]
        elif code == MplPath.LINETO:
            current.append((float(vertices[0]), float(vertices[1])))
        elif code == MplPath.CLOSEPOLY:
            if len(current) >= 2:
                current.append(current[0])
                strokes.append(np.array(current, dtype=float))
            current = []

    if len(current) >= 2:
        strokes.append(np.array(current, dtype=float))
    return strokes


def _bounds(strokes: list[Stroke]) -> tuple[float, float, float, float] | None:
    if not strokes:
        return None
    points = np.vstack(strokes)
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    return float(mins[0]), float(mins[1]), float(maxs[0]), float(maxs[1])


def _perturb(stroke: Stroke, rng: np.random.Generator, jitter: float, wobble: float) -> Stroke:
    if len(stroke) <= 2 or (jitter <= 0 and wobble <= 0):
        return stroke

    out = stroke.copy()
    t = np.linspace(0.0, np.pi * 2.0, len(stroke))
    phase = rng.uniform(0.0, np.pi * 2.0)
    out[:, 0] += np.sin(t + phase) * wobble
    out[:, 1] += np.cos(t * 1.7 + phase) * wobble
    out[1:-1] += rng.normal(0.0, jitter, size=(len(stroke) - 2, 2))
    return out


class TextRenderer:
    """Render plain text into paper-coordinate strokes."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        self.font = _find_font(self.config.font_name, self.config.font_path)
        self._rng = np.random.default_rng(self.config.seed)

    def render(self, text: str) -> list[Stroke]:
        cfg = self.config
        size_pt = cfg.font_size / PT_TO_MM
        line_advance = cfg.font_size * cfg.line_height
        x = cfg.margin_left
        baseline = cfg.paper_height - cfg.margin_top - cfg.font_size
        strokes: list[Stroke] = []

        for char in text:
            if char == "\n":
                x = cfg.margin_left
                baseline -= line_advance
                continue
            if char.isspace():
                x += cfg.font_size * 0.55
                continue

            char_path = TextPath((0, 0), char, size=size_pt, prop=self.font)
            char_strokes = [s * PT_TO_MM for s in _flatten_text_path(char_path)]
            box = _bounds(char_strokes)
            if box is None:
                x += cfg.font_size * 0.55
                continue

            min_x, min_y, max_x, _max_y = box
            width = max_x - min_x
            if x > cfg.margin_left and x + width > cfg.margin_left + cfg.content_width:
                x = cfg.margin_left
                baseline -= line_advance

            baseline_shift = self._rng.normal(0.0, cfg.font_size * 0.035)
            for stroke in char_strokes:
                placed = stroke.copy()
                placed[:, 0] += x - min_x
                placed[:, 1] += baseline - min_y + baseline_shift
                strokes.append(_perturb(placed, self._rng, cfg.jitter, cfg.wobble))

            x += width + cfg.char_spacing

        return strokes


def render_text(text: str, config: RenderConfig | None = None) -> list[Stroke]:
    return TextRenderer(config).render(text)

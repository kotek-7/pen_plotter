from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

Point = tuple[float, float]


@dataclass(frozen=True)
class PreviewConfig:
    paper_width: float = 210.0
    paper_height: float = 297.0
    scale: float = 3.0
    stroke_color: str = "#1f2937"
    stroke_width: float = 1.8
    show_travel: bool = True
    travel_color: str = "#c9bda3"
    travel_width: float = 0.6


def trajectory_to_svg(
    trajectory: Sequence[dict[str, Any]],
    config: PreviewConfig | None = None,
) -> str:
    """Render a paper-coordinate trajectory as a preview SVG.

    The trajectory is the canonical ``x, y, t, pen_state, pressure`` representation.
    Pen-down runs become solid strokes; pen-up runs are optional faint travels.
    Paper coordinates are Y-UP, so the Y axis is flipped only at draw time.
    """
    config = config or PreviewConfig()
    scale = config.scale
    width = config.paper_width * scale
    height = config.paper_height * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#f8f5e9"/>',
        f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" '
        'fill="none" stroke="#999" stroke-width="1"/>',
    ]

    if config.show_travel:
        for travel in _pen_up_runs(trajectory):
            parts.append(_path(travel, config, color=config.travel_color, width=config.travel_width, dashed=True))

    for stroke in _pen_down_runs(trajectory):
        parts.append(_path(stroke, config, color=config.stroke_color, width=config.stroke_width))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _pen_down_runs(trajectory: Sequence[dict[str, Any]]) -> list[list[Point]]:
    return _runs(trajectory, pen_state=1)


def _pen_up_runs(trajectory: Sequence[dict[str, Any]]) -> list[list[Point]]:
    return _runs(trajectory, pen_state=0)


def _runs(trajectory: Sequence[dict[str, Any]], *, pen_state: int) -> list[list[Point]]:
    runs: list[list[Point]] = []
    current: list[Point] = []
    for point in trajectory:
        if int(point.get("pen_state", 0)) == pen_state:
            current.append((float(point["x"]), float(point["y"])))
        elif len(current) >= 2:
            runs.append(current)
            current = []
        else:
            current = []
    if len(current) >= 2:
        runs.append(current)
    return runs


def _path(
    points: list[Point],
    config: PreviewConfig,
    *,
    color: str,
    width: float,
    dashed: bool = False,
) -> str:
    scale = config.scale
    d = " ".join(
        f"{'M' if i == 0 else 'L'} {x * scale:.2f} {(config.paper_height - y) * scale:.2f}"
        for i, (x, y) in enumerate(points)
    )
    dash = ' stroke-dasharray="3 4"' if dashed else ""
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{dash}/>'
    )

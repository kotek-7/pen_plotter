from __future__ import annotations

from typing import Any

from scribing_plotter.config import PlotterConfig


def validate_gcode(lines: list[str], config: PlotterConfig | None = None) -> dict[str, Any]:
    """Minimal range check that G-code stays within paper, Z, and feed limits."""
    config = config or PlotterConfig()
    violations: list[str] = []
    z_values: list[float] = []
    feed_values: list[int] = []

    for line in lines:
        if line.startswith("G92"):
            continue
        for axis, low, high in (("X", 0.0, config.paper_width), ("Y", 0.0, config.paper_height)):
            value = _axis_value(line, axis)
            if value is not None and not low <= value <= high:
                violations.append(f"{axis.lower()}-out-of-range:{value}")
        z = _axis_value(line, "Z")
        if z is not None:
            z_values.append(z)
            if not config.pen_up_z <= z <= config.pen_down_z:
                violations.append(f"z-out-of-range:{z}")
        feed = _feed_value(line)
        if feed is not None:
            feed_values.append(feed)
            if feed <= 0 or feed > config.travel_speed:
                violations.append(f"feed-out-of-range:{feed}")

    return {
        "ok": not violations,
        "violations": violations,
        "line_count": len(lines),
        "z_min": min(z_values) if z_values else None,
        "z_max": max(z_values) if z_values else None,
        "feed_min": min(feed_values) if feed_values else None,
        "feed_max": max(feed_values) if feed_values else None,
    }


def _axis_value(line: str, axis: str) -> float | None:
    for part in line.split():
        if part.startswith(axis):
            try:
                return float(part[1:])
            except ValueError:
                return None
    return None


def _feed_value(line: str) -> int | None:
    for part in line.split():
        if part.startswith("F"):
            return int(float(part[1:]))
    return None

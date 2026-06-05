from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


Point = dict[str, Any]


def compute_trajectory_metrics(points: Sequence[Point]) -> dict[str, float | int | str]:
    if not points:
        return {
            "point_count": 0,
            "stroke_count": 0,
            "duration_ms": 0,
            "draw_distance_mm": 0.0,
            "penup_distance_mm": 0.0,
            "velocity_peak_count": 0,
            "status": "empty",
        }

    ordered = sorted(points, key=lambda p: float(p.get("t", 0.0)))
    draw_distance = 0.0
    penup_distance = 0.0
    stroke_count = 0
    was_down = False
    speeds: list[float] = []

    for prev, curr in zip(ordered, ordered[1:], strict=False):
        prev_down = int(prev.get("pen_state", 0)) == 1
        curr_down = int(curr.get("pen_state", 0)) == 1
        dist = _distance(prev, curr)
        dt_ms = max(float(curr.get("t", 0.0)) - float(prev.get("t", 0.0)), 0.0)
        if curr_down:
            draw_distance += dist
        else:
            penup_distance += dist
        if prev_down and curr_down and dt_ms > 0:
            speeds.append(dist / (dt_ms / 1000.0))

    for point in ordered:
        is_down = int(point.get("pen_state", 0)) == 1
        if is_down and not was_down:
            stroke_count += 1
        was_down = is_down

    duration = int(float(ordered[-1].get("t", 0.0)) - float(ordered[0].get("t", 0.0)))
    return {
        "point_count": len(ordered),
        "stroke_count": stroke_count,
        "duration_ms": max(duration, 0),
        "draw_distance_mm": round(draw_distance, 4),
        "penup_distance_mm": round(penup_distance, 4),
        "velocity_peak_count": _count_local_peaks(speeds),
        "mean_draw_speed_mm_s": round(sum(speeds) / len(speeds), 4) if speeds else 0.0,
        "status": "ok",
    }


def _distance(a: Point, b: Point) -> float:
    ax = float(a.get("x", a.get("x_mm", 0.0)))
    ay = float(a.get("y", a.get("y_mm", 0.0)))
    bx = float(b.get("x", b.get("x_mm", 0.0)))
    by = float(b.get("y", b.get("y_mm", 0.0)))
    return math.hypot(bx - ax, by - ay)


def _count_local_peaks(values: Sequence[float]) -> int:
    if len(values) < 3:
        return 0
    return sum(1 for a, b, c in zip(values, values[1:], values[2:], strict=False) if a < b > c)

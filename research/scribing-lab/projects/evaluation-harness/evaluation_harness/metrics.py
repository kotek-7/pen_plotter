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
            "mean_draw_speed_mm_s": 0.0,
            "max_draw_speed_mm_s": 0.0,
            "draw_speed_cv": 0.0,
            "mean_abs_acceleration_mm_s2": 0.0,
            "mean_abs_jerk_mm_s3": 0.0,
            "status": "empty",
        }

    ordered = sorted(points, key=lambda p: float(p.get("t", 0.0)))
    draw_distance = 0.0
    penup_distance = 0.0
    stroke_count = 0
    was_down = False
    speeds: list[float] = []
    speed_times_s: list[float] = []

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
            speed_times_s.append(float(curr.get("t", 0.0)) / 1000.0)

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
        "max_draw_speed_mm_s": round(max(speeds), 4) if speeds else 0.0,
        "draw_speed_cv": _coefficient_of_variation(speeds),
        "mean_abs_acceleration_mm_s2": _mean_abs_derivative(speeds, speed_times_s),
        "mean_abs_jerk_mm_s3": _mean_abs_second_derivative(speeds, speed_times_s),
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


def _coefficient_of_variation(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return round(math.sqrt(variance) / mean, 4)


def _mean_abs_derivative(values: Sequence[float], times_s: Sequence[float]) -> float:
    derivatives = _derivatives(values, times_s)
    if not derivatives:
        return 0.0
    return round(sum(abs(value) for value in derivatives) / len(derivatives), 4)


def _mean_abs_second_derivative(values: Sequence[float], times_s: Sequence[float]) -> float:
    derivatives = _derivatives(values, times_s)
    derivative_times = list(times_s[1:])
    second = _derivatives(derivatives, derivative_times)
    if not second:
        return 0.0
    return round(sum(abs(value) for value in second) / len(second), 4)


def _derivatives(values: Sequence[float], times_s: Sequence[float]) -> list[float]:
    out: list[float] = []
    for prev_value, curr_value, prev_t, curr_t in zip(
        values,
        values[1:],
        times_s,
        times_s[1:],
        strict=False,
    ):
        dt = curr_t - prev_t
        if dt <= 0:
            continue
        out.append((curr_value - prev_value) / dt)
    return out

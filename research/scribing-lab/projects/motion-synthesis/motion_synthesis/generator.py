from __future__ import annotations

import math
import random
from dataclasses import dataclass

from motion_synthesis.models import MotionPoint, Point, SkeletonStroke


@dataclass(frozen=True)
class MotionConfig:
    draw_speed_mm_s: float = 40.0
    penup_speed_mm_s: float = 120.0
    samples_per_segment: int = 6
    min_segment_duration_ms: int = 12
    timing_jitter_cv: float = 0.08
    tremor_mm: float = 0.015
    harai_min_pressure: float = 0.2
    hane_min_pressure: float = 0.25
    tome_terminal_pressure: float = 1.05


def synthesize_motion(
    strokes: list[SkeletonStroke],
    *,
    seed: int,
    config: MotionConfig | None = None,
) -> list[MotionPoint]:
    cfg = config or MotionConfig()
    t_ms = 0.0
    current = (0.0, 297.0)
    trajectory = [MotionPoint(x=current[0], y=current[1], t=0, pen_state=0, pressure=0.0)]
    literal_counts: dict[str, int] = {}

    for stroke in strokes:
        if len(stroke.points) < 2:
            continue
        occurrence_index = literal_counts.get(stroke.literal, 0)
        literal_counts[stroke.literal] = occurrence_index + 1
        stroke_rng = _stroke_rng(seed, stroke, occurrence_index)
        stroke_draw_speed = _stroke_draw_speed(cfg, stroke)
        stroke_penup_speed = _stroke_penup_speed(cfg, stroke)
        stroke_tremor = _stroke_tremor(cfg, stroke)
        start = stroke.points[0]
        t_ms += _duration_ms(_distance(current, start), stroke_penup_speed, stroke_rng, cfg)
        trajectory.append(_point(start, t_ms, pen_state=0, pressure=0.0))
        trajectory.append(_point(start, t_ms, pen_state=1, pressure=0.9))

        sampled = _sample_stroke_points(stroke.points, cfg.samples_per_segment)
        segment_distances = [
            _distance(prev, curr) for prev, curr in zip(sampled, sampled[1:], strict=False)
        ]
        weights = _speed_profile_weights(len(segment_distances), stroke=stroke)
        pressure = _pressure_profile(stroke.terminal, len(sampled), cfg, stroke=stroke)

        for i, point in enumerate(sampled[1:], start=1):
            duration = _duration_ms(
                segment_distances[i - 1] * weights[i - 1],
                stroke_draw_speed,
                stroke_rng,
                cfg,
            )
            t_ms += max(duration, cfg.min_segment_duration_ms)
            px, py = _apply_tremor(point, i, len(sampled), stroke_rng, stroke_tremor)
            trajectory.append(
                MotionPoint(
                    x=round(px, 4),
                    y=round(py, 4),
                    t=int(round(t_ms)),
                    pen_state=1,
                    pressure=round(pressure[i], 4),
                )
            )

        last = sampled[-1]
        trajectory.append(_point(last, t_ms, pen_state=0, pressure=0.0))
        current = last

    return trajectory


def _sample_stroke_points(points: tuple[Point, ...], samples_per_segment: int) -> list[Point]:
    sampled = [points[0]]
    for start, end in zip(points, points[1:], strict=False):
        for i in range(1, samples_per_segment + 1):
            r = i / samples_per_segment
            sampled.append((start[0] + (end[0] - start[0]) * r, start[1] + (end[1] - start[1]) * r))
    return sampled


def _speed_profile_weights(n_segments: int, *, stroke: SkeletonStroke) -> list[float]:
    if n_segments <= 0:
        return []
    weights: list[float] = []
    terminal_slowdown = 0.05 if stroke.terminal == "harai" else 0.0
    terminal_slowdown += 0.04 if stroke.terminal == "hane" else 0.0
    occurrence_bias = min(stroke.repeat_index, 3) * 0.03
    line_bias = min(stroke.line_index, 4) * 0.015
    for i in range(n_segments):
        phase = i / max(n_segments - 1, 1)
        # 小さいほど速い。始筆と終筆を遅くし、中盤を速くする。
        ease_in = phase**1.8
        ease_out = (1.0 - phase) ** 1.6
        peak = math.sin(math.pi * phase)
        asymmetry = math.sin((phase - 0.15) * math.pi)
        weights.append(
            1.42
            - 0.58 * peak
            + 0.09 * (ease_in + ease_out)
            + 0.03 * asymmetry
            + terminal_slowdown * (1.0 - phase)
            + occurrence_bias * phase
            + line_bias * phase
        )
    return weights


def _pressure_profile(
    terminal: str,
    n_points: int,
    cfg: MotionConfig,
    *,
    stroke: SkeletonStroke,
) -> list[float]:
    if n_points <= 0:
        return []
    pressure = [1.0 for _ in range(n_points)]
    tail = max(2, min(5, n_points))
    repeat_bias = min(stroke.repeat_index, 3) * 0.025
    line_bias = min(stroke.line_index, 4) * 0.015
    for i in range(n_points - tail, n_points):
        r = (i - (n_points - tail)) / max(tail - 1, 1)
        if terminal == "harai":
            pressure[i] = 1.0 - (1.0 - cfg.harai_min_pressure - repeat_bias) * r
        elif terminal == "hane":
            pressure[i] = 1.05 - (1.05 - cfg.hane_min_pressure - repeat_bias) * (r**0.7)
        elif terminal == "tome":
            pressure[i] = 1.0 + (cfg.tome_terminal_pressure + line_bias - 1.0) * r
    return pressure


def _duration_ms(distance_mm: float, speed_mm_s: float, rng: random.Random, cfg: MotionConfig) -> float:
    if speed_mm_s <= 0:
        raise ValueError("speed_mm_s must be positive")
    base = distance_mm / speed_mm_s * 1000.0
    jitter = rng.gauss(1.0, cfg.timing_jitter_cv)
    return base * max(0.65, min(1.35, jitter))


def _stroke_rng(seed: int, stroke: SkeletonStroke, occurrence_index: int) -> random.Random:
    return random.Random(
        f"{seed}:{stroke.literal}:{occurrence_index}:{stroke.stroke_type}:{stroke.terminal}:"
        f"{stroke.char_index}:{stroke.line_index}:{stroke.line_char_index}:{stroke.repeat_index}:"
        f"{len(stroke.points)}"
    )


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _apply_tremor(point: Point, index: int, total: int, rng: random.Random, tremor_mm: float) -> Point:
    if index == 0 or index == total - 1 or tremor_mm <= 0:
        return point
    return (
        point[0] + rng.gauss(0.0, tremor_mm),
        point[1] + rng.gauss(0.0, tremor_mm),
    )


def _point(point: Point, t_ms: float, *, pen_state: int, pressure: float) -> MotionPoint:
    return MotionPoint(
        x=round(point[0], 4),
        y=round(point[1], 4),
        t=int(round(t_ms)),
        pen_state=pen_state,
        pressure=round(pressure, 4),
    )


def _stroke_draw_speed(cfg: MotionConfig, stroke: SkeletonStroke) -> float:
    slowdown = 1.0 + min(stroke.line_index, 4) * 0.025 + min(stroke.repeat_index, 3) * 0.02
    if stroke.terminal == "harai":
        slowdown += 0.03
    elif stroke.terminal == "hane":
        slowdown += 0.015
    return max(1.0, cfg.draw_speed_mm_s / slowdown)


def _stroke_penup_speed(cfg: MotionConfig, stroke: SkeletonStroke) -> float:
    slowdown = 1.0 + min(stroke.line_index, 4) * 0.015 + min(stroke.char_index, 8) * 0.005
    return max(1.0, cfg.penup_speed_mm_s / slowdown)


def _stroke_tremor(cfg: MotionConfig, stroke: SkeletonStroke) -> float:
    scale = 1.0 + min(stroke.line_index, 4) * 0.08 + min(stroke.repeat_index, 3) * 0.06
    if stroke.terminal == "hane":
        scale += 0.04
    return max(0.0, cfg.tremor_mm * scale)

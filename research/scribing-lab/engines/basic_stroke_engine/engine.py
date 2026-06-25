from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


ENGINE_ID = "basic-stroke-engine"


@dataclass(frozen=True)
class EngineConfig:
    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_size: float = 9.0
    char_spacing: float = 2.0
    line_height: float = 1.45
    draw_speed_mm_s: float = 35.0
    penup_speed_mm_s: float = 120.0


def generate(request: dict[str, Any]) -> dict[str, Any]:
    text = str(request.get("text", ""))
    seed = int(request.get("seed", 1))
    params = dict(request.get("params", {}))
    config = _config_from_params(params)

    strokes = _layout_text(text, seed=seed, config=config)
    trajectory = _strokes_to_trajectory(strokes, config=config)

    return {
        "engine_id": ENGINE_ID,
        "engine_parameters": {
            "seed": seed,
            "config": config.__dict__,
            "params": params,
        },
        "trajectory": trajectory,
    }


def _config_from_params(params: dict[str, Any]) -> EngineConfig:
    values = EngineConfig().__dict__.copy()
    for key, raw in params.items():
        if key not in values:
            continue
        base = values[key]
        if isinstance(base, int):
            values[key] = int(raw)
        else:
            values[key] = float(raw)
    return EngineConfig(**values)


def _layout_text(
    text: str,
    *,
    seed: int,
    config: EngineConfig,
) -> list[list[tuple[float, float]]]:
    strokes: list[list[tuple[float, float]]] = []
    x = config.margin_left
    y_top = config.paper_height - config.margin_top
    line_advance = config.char_size * config.line_height
    max_x = config.paper_width - config.margin_left

    for index, char in enumerate(text):
        if char == "\n":
            x = config.margin_left
            y_top -= line_advance
            continue
        if char.isspace():
            x += config.char_size * 0.55
            continue
        if x + config.char_size > max_x:
            x = config.margin_left
            y_top -= line_advance

        strokes.extend(_character_strokes(char, index=index, x=x, y_top=y_top, seed=seed, size=config.char_size))
        x += config.char_size + config.char_spacing

    return strokes


def _character_strokes(
    char: str,
    *,
    index: int,
    x: float,
    y_top: float,
    seed: int,
    size: float,
) -> list[list[tuple[float, float]]]:
    rng = random.Random(f"{seed}:{index}:{char}")
    left = x
    right = x + size
    top = y_top
    mid_x = x + size * (0.48 + rng.uniform(-0.08, 0.08))
    mid_y = y_top - size * (0.52 + rng.uniform(-0.08, 0.08))
    bottom = y_top - size

    code = ord(char)
    candidates = [
        [(left, top), (right, top)],
        [(left, bottom), (right, bottom)],
        [(left, top), (left, bottom)],
        [(right, top), (right, bottom)],
        [(left, mid_y), (right, mid_y)],
        [(mid_x, top), (mid_x, bottom)],
        [(left, top), (right, bottom)],
        [(left, bottom), (right, top)],
        [(left, mid_y), (mid_x, top), (right, mid_y)],
        [(left, mid_y), (mid_x, bottom), (right, mid_y)],
    ]
    count = 2 + (code % 3)
    start = code % len(candidates)
    selected = [candidates[(start + i * 3) % len(candidates)] for i in range(count)]
    return [_jitter_stroke(stroke, rng=rng, amount=size * 0.025) for stroke in selected]


def _jitter_stroke(
    stroke: list[tuple[float, float]],
    *,
    rng: random.Random,
    amount: float,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i, (x, y) in enumerate(stroke):
        if i == 0 or i == len(stroke) - 1:
            out.append((round(x, 4), round(y, 4)))
            continue
        out.append((round(x + rng.uniform(-amount, amount), 4), round(y + rng.uniform(-amount, amount), 4)))
    return out


def _strokes_to_trajectory(
    strokes: list[list[tuple[float, float]]],
    *,
    config: EngineConfig,
) -> list[dict[str, float | int]]:
    t_ms = 0.0
    current = (0.0, config.paper_height)
    points: list[dict[str, float | int]] = [_point(current, t_ms, pen_state=0, pressure=0.0)]

    for stroke in strokes:
        if len(stroke) < 2:
            continue
        start = stroke[0]
        t_ms += _duration_ms(_distance(current, start), config.penup_speed_mm_s)
        points.append(_point(start, t_ms, pen_state=0, pressure=0.0))
        points.append(_point(start, t_ms, pen_state=1, pressure=0.9))

        sampled = _sample_polyline(stroke, samples_per_segment=6)
        for i, point in enumerate(sampled[1:], start=1):
            prev = sampled[i - 1]
            t_ms += max(_duration_ms(_distance(prev, point), config.draw_speed_mm_s), 10.0)
            phase = i / max(len(sampled) - 1, 1)
            pressure = 0.9 + 0.1 * math.sin(math.pi * phase)
            if i == len(sampled) - 1:
                pressure = 0.45
            points.append(_point(point, t_ms, pen_state=1, pressure=pressure))

        points.append(_point(sampled[-1], t_ms, pen_state=0, pressure=0.0))
        current = sampled[-1]

    return points


def _sample_polyline(
    stroke: list[tuple[float, float]],
    *,
    samples_per_segment: int,
) -> list[tuple[float, float]]:
    sampled = [stroke[0]]
    for start, end in zip(stroke, stroke[1:], strict=False):
        for i in range(1, samples_per_segment + 1):
            r = i / samples_per_segment
            sampled.append((start[0] + (end[0] - start[0]) * r, start[1] + (end[1] - start[1]) * r))
    return sampled


def _point(
    point: tuple[float, float],
    t_ms: float,
    *,
    pen_state: int,
    pressure: float,
) -> dict[str, float | int]:
    return {
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        "t": int(round(t_ms)),
        "pen_state": pen_state,
        "pressure": round(pressure, 4),
    }


def _duration_ms(distance_mm: float, speed_mm_s: float) -> float:
    if speed_mm_s <= 0:
        raise ValueError("speed_mm_s must be positive")
    return distance_mm / speed_mm_s * 1000.0


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])

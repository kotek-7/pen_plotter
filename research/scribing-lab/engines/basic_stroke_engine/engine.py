from __future__ import annotations

import html
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
    pen_up_z: float = 0.5
    pen_down_z: float = 3.5
    travel_feed: int = 5000
    min_draw_feed: int = 300
    max_draw_feed: int = 1800


def generate(request: dict[str, Any]) -> dict[str, Any]:
    text = str(request.get("text", ""))
    seed = int(request.get("seed", 1))
    params = dict(request.get("params", {}))
    config = _config_from_params(params)

    strokes = _layout_text(text, seed=seed, config=config)
    trajectory = _strokes_to_trajectory(strokes, config=config)
    gcode = _export_gcode(trajectory, config=config)
    safety = _validate_gcode(gcode, config=config)
    preview_svg = _render_preview_svg(
        text=text,
        strokes=strokes,
        config=config,
    )

    return {
        "engine_id": ENGINE_ID,
        "engine_parameters": {
            "seed": seed,
            "config": config.__dict__,
            "params": params,
        },
        "trajectory": trajectory,
        "preview_svg": preview_svg,
        "gcode": gcode,
        "safety": safety,
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


def _export_gcode(
    trajectory: list[dict[str, float | int]],
    *,
    config: EngineConfig,
) -> list[str]:
    lines = [
        "; Generated by basic-stroke-engine",
        "$H",
        "G4 P1",
        f"G92 X0 Y{config.paper_height:.0f} Z0",
        "G90",
        _z_command(config.pen_up_z, config),
    ]
    pen_down = False
    prev: dict[str, float | int] | None = None

    for point in trajectory:
        x = float(point["x"])
        y = float(point["y"])
        down = int(point["pen_state"]) == 1
        if not down:
            if pen_down:
                lines.append(_z_command(config.pen_up_z, config))
                pen_down = False
            if prev is None or (float(prev["x"]), float(prev["y"])) != (x, y):
                lines.append(f"G0 X{x:.2f} Y{y:.2f} F{config.travel_feed}")
            prev = point
            continue

        z = config.pen_down_z - (config.pen_down_z - 2.0) * (1.0 - float(point["pressure"]))
        z = min(config.pen_down_z, max(2.0, z))
        if not pen_down:
            lines.append(f"G0 X{x:.2f} Y{y:.2f} F{config.travel_feed}")
            lines.append(_z_command(z, config))
            pen_down = True
            prev = point
            continue

        feed = _feed(prev, point, config) if prev is not None else config.min_draw_feed
        lines.append(f"G1 X{x:.2f} Y{y:.2f} Z{z:.2f} F{feed}")
        prev = point

    lines.extend(
        [
            _z_command(config.pen_up_z, config),
            f"G0 X5 Y{config.paper_height - 5:.0f} F{config.travel_feed}",
        ]
    )
    return lines


def _validate_gcode(lines: list[str], *, config: EngineConfig) -> dict[str, Any]:
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
            if feed <= 0 or feed > config.travel_feed:
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


def _render_preview_svg(
    *,
    text: str,
    strokes: list[list[tuple[float, float]]],
    config: EngineConfig,
) -> str:
    scale = 3.0
    width = config.paper_width * scale
    height = config.paper_height * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#f8f5e9"/>',
        f'<rect x="0" y="0" width="{config.paper_width * scale:.2f}" height="{config.paper_height * scale:.2f}" fill="none" stroke="#999" stroke-width="1"/>',
        f'<text x="12" y="20" font-size="12" fill="#666">{html.escape(text[:80])}</text>',
    ]
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        d = " ".join(
            f"{'M' if i == 0 else 'L'} {x * scale:.2f} {(config.paper_height - y) * scale:.2f}"
            for i, (x, y) in enumerate(stroke)
        )
        parts.append(f'<path d="{d}" fill="none" stroke="#1f2937" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


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


def _feed(
    prev: dict[str, float | int],
    curr: dict[str, float | int],
    config: EngineConfig,
) -> int:
    dt_ms = max(float(curr["t"]) - float(prev["t"]), 1.0)
    dist = _distance((float(prev["x"]), float(prev["y"])), (float(curr["x"]), float(curr["y"])))
    feed = int(dist / (dt_ms / 1000.0) * 60.0)
    return max(config.min_draw_feed, min(config.max_draw_feed, feed))


def _z_command(z: float, config: EngineConfig) -> str:
    return f"G1G90 Z{z:.2f} F{config.travel_feed}"


def _axis_value(line: str, axis: str) -> float | None:
    for part in line.split():
        if part.startswith(axis):
            return float(part[1:])
    return None


def _feed_value(line: str) -> int | None:
    for part in line.split():
        if part.startswith("F"):
            return int(float(part[1:]))
    return None


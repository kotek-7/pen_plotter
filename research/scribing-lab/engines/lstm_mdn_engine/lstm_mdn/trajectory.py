from __future__ import annotations

import math

Stroke = list[tuple[float, float]]


def map_to_paper(strokes: list[Stroke], *, origin_x: float, top_y: float, size: float) -> list[Stroke]:
    """セル正規化座標 (y-down) を紙面 mm (Y-up) へ写す。"""
    out: list[Stroke] = []
    for stroke in strokes:
        out.append([(origin_x + x * size, top_y - y * size) for x, y in stroke])
    return out


def _point(p: tuple[float, float], t_ms: float, pen_state: int, pressure: float) -> dict:
    return {
        "x": round(p[0], 4),
        "y": round(p[1], 4),
        "t": int(round(t_ms)),
        "pen_state": pen_state,
        "pressure": round(pressure, 4),
    }


def append_canonical(
    out: list[dict],
    strokes_mm: list[Stroke],
    *,
    t_start: float,
    last_pos: tuple[float, float],
    draw_speed_mm_s: float,
    penup_speed_mm_s: float,
) -> tuple[float, tuple[float, float]]:
    """紙面 mm のストローク列を canonical trajectory として out に追記する。"""
    t = t_start
    cur = last_pos
    for stroke in strokes_mm:
        if len(stroke) < 2:
            continue
        start = stroke[0]
        t += math.dist(cur, start) / penup_speed_mm_s * 1000.0
        out.append(_point(start, t, 0, 0.0))
        out.append(_point(start, t, 1, 1.0))
        for prev, p in zip(stroke, stroke[1:], strict=False):
            t += math.dist(prev, p) / draw_speed_mm_s * 1000.0
            out.append(_point(p, t, 1, 1.0))
        end = stroke[-1]
        out.append(_point(end, t, 0, 0.0))
        cur = end
    return t, cur


def render_svg(samples: list[list[Stroke]], *, cols: int = 5, cell_px: float = 120.0, pad: float = 12.0) -> str:
    """セル正規化座標のサンプル群をグリッド配置した確認用 SVG を返す。"""
    n = len(samples)
    cols = max(1, min(cols, n)) if n else 1
    rows = math.ceil(n / cols) if n else 1
    width = cols * cell_px
    height = rows * cell_px
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    inner = cell_px - 2 * pad
    for i, strokes in enumerate(samples):
        gx = (i % cols) * cell_px
        gy = (i // cols) * cell_px
        parts.append(
            f'<rect x="{gx + pad:.1f}" y="{gy + pad:.1f}" width="{inner:.1f}" height="{inner:.1f}" '
            'fill="none" stroke="#e2e0d6"/>'
        )
        for stroke in strokes:
            d = " ".join(
                f"{'M' if k == 0 else 'L'} {gx + pad + x * inner:.1f} {gy + pad + y * inner:.1f}"
                for k, (x, y) in enumerate(stroke)
            )
            parts.append(
                f'<path d="{d}" fill="none" stroke="#1f2937" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/>'
            )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"

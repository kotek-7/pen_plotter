from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AugmentParams:
    """拡張強度 (deep-research §8 の推奨に準拠した保守的な既定)。

    平行移動・反転・stroke 順序変更は行わない (文字同一性・構造を保つため)。
    """

    rotate_deg: float = 3.0  # 回転 ±deg
    scale: float = 0.10  # 拡縮 1±scale (x/y 独立)
    shear: float = 0.05  # せん断 ±
    jitter: float = 0.3  # 点ごとの微小ガウスノイズ (canvas px)


def _cell_center(sample: dict[str, Any]) -> tuple[float, float]:
    cell = (sample.get("guide") or {}).get("cell")
    if cell:
        return cell["x"] + cell["width"] / 2.0, cell["y"] + cell["height"] / 2.0
    canvas = sample.get("canvas") or {}
    return float(canvas.get("width", 100)) / 2.0, float(canvas.get("height", 100)) / 2.0


def _augment_once(
    sample: dict[str, Any], rng: random.Random, params: AugmentParams, index: int
) -> dict[str, Any]:
    cx, cy = _cell_center(sample)
    rot = math.radians(rng.uniform(-params.rotate_deg, params.rotate_deg))
    sx = rng.uniform(1.0 - params.scale, 1.0 + params.scale)
    sy = rng.uniform(1.0 - params.scale, 1.0 + params.scale)
    sh = rng.uniform(-params.shear, params.shear)
    cos, sin = math.cos(rot), math.sin(rot)

    def transform(x: float, y: float) -> tuple[float, float]:
        px, py = x - cx, y - cy
        px, py = px * sx, py * sy  # scale
        px = px + sh * py  # shear (x)
        rx = px * cos - py * sin  # rotate
        ry = px * sin + py * cos
        jx = rng.gauss(0.0, params.jitter) if params.jitter > 0 else 0.0
        jy = rng.gauss(0.0, params.jitter) if params.jitter > 0 else 0.0
        return cx + rx + jx, cy + ry + jy

    def transform_point(point: dict[str, Any]) -> dict[str, Any]:
        nx, ny = transform(float(point["x"]), float(point["y"]))
        return {**point, "x": round(nx, 4), "y": round(ny, 4)}

    new = dict(sample)
    new["strokes"] = [
        {**stroke, "points": [transform_point(p) for p in stroke["points"]]}
        for stroke in sample["strokes"]
    ]
    orig_id = str(sample.get("sampleId", ""))
    new["sampleId"] = f"{orig_id}_aug{index:02d}"
    new["augmentedFrom"] = orig_id
    new["augment"] = {
        "rotate_deg": round(math.degrees(rot), 3),
        "scale_x": round(sx, 4),
        "scale_y": round(sy, 4),
        "shear": round(sh, 4),
        "jitter": params.jitter,
    }
    return new


def augment_dataset(
    samples: list[dict[str, Any]],
    *,
    copies: int,
    params: AugmentParams,
    seed: int,
    include_originals: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if include_originals:
        out.extend(samples)
    for i, sample in enumerate(samples):
        # サンプルごとに決定論的な rng (sampleId をキーに)。
        rng = random.Random(f"{seed}:{sample.get('sampleId', i)}")
        for k in range(copies):
            out.append(_augment_once(sample, rng, params, k))
    return out

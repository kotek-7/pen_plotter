from __future__ import annotations

import glob
import json
import math
from dataclasses import dataclass

import numpy as np

from .config import PEN_DOWN, PEN_END, PEN_UP

Point = tuple[float, float]


@dataclass
class Dataset:
    """前処理済みデータセット。

    sequences[i] は (T_i, 5) 配列で各行 (dx_std, dy_std, pen_onehot[3])。
    dx,dy はデータセット標準偏差で標準化済み。
    """

    sequences: list[np.ndarray]
    char_ids: list[int]
    chars: list[str]  # id -> literal
    dxdy_std: tuple[float, float]


def load_raw(dataset_glob: str) -> list[dict]:
    paths = sorted(glob.glob(dataset_glob))
    if not paths:
        raise FileNotFoundError(f"no dataset files matched: {dataset_glob}")
    samples: list[dict] = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    return samples


def _resample_stroke(points: list[Point], step: float) -> list[Point]:
    """弧長を一定間隔でサンプリングする (端点は保持)。"""
    if len(points) < 2:
        return list(points)
    seg = [math.dist(points[k], points[k + 1]) for k in range(len(points) - 1)]
    total = sum(seg)
    if total <= 1e-9:
        return [points[0]]
    cum = [0.0]
    for length in seg:
        cum.append(cum[-1] + length)
    n = max(1, round(total / step))
    out: list[Point] = []
    idx = 0
    for i in range(n + 1):
        target = total * i / n
        while idx < len(seg) - 1 and cum[idx + 1] < target:
            idx += 1
        seg_len = seg[idx] if seg[idx] > 1e-9 else 1e-9
        r = (target - cum[idx]) / seg_len
        a, b = points[idx], points[idx + 1]
        out.append((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r))
    return out


def _sample_to_points(sample: dict, step: float) -> list[tuple[float, float, int]]:
    """1 サンプルを guide.cell 正規化 + 弧長リサンプルし、(x, y, stroke_index) 列にする。"""
    cell = sample["guide"]["cell"]
    cx, cy, cw, ch = cell["x"], cell["y"], cell["width"], cell["height"]
    sw = cw if cw > 1e-9 else 1.0
    sh = ch if ch > 1e-9 else 1.0
    out: list[tuple[float, float, int]] = []
    for si, stroke in enumerate(sample["strokes"]):
        pts = [((p["x"] - cx) / sw, (p["y"] - cy) / sh) for p in stroke["points"]]
        for x, y in _resample_stroke(pts, step):
            out.append((x, y, si))
    return out


def _points_to_sequence(points: list[tuple[float, float, int]]) -> np.ndarray:
    """(x,y,stroke) 列 → (T, 5) の (dx, dy, pen_onehot)。標準化前。"""
    rows: list[list[float]] = []
    # 先頭点: 移動なし・接地
    rows.append([0.0, 0.0, *_onehot(PEN_DOWN)])
    for i in range(1, len(points)):
        px, py, ps = points[i - 1]
        x, y, s = points[i]
        pen = PEN_UP if s != ps else PEN_DOWN
        rows.append([x - px, y - py, *_onehot(pen)])
    rows.append([0.0, 0.0, *_onehot(PEN_END)])
    return np.asarray(rows, dtype=np.float32)


def _onehot(pen: int) -> list[float]:
    vec = [0.0, 0.0, 0.0]
    vec[pen] = 1.0
    return vec


def build_dataset(dataset_glob: str, *, step: float) -> Dataset:
    samples = load_raw(dataset_glob)
    raw_seqs: list[np.ndarray] = []
    chars_per_sample: list[str] = []
    for sample in samples:
        points = _sample_to_points(sample, step)
        if len(points) < 2:
            continue
        raw_seqs.append(_points_to_sequence(points))
        chars_per_sample.append(sample["char"])

    if not raw_seqs:
        raise ValueError("no usable samples after preprocessing")

    # dx,dy の標準偏差で標準化 (offset は平均ほぼ 0 なので除算のみ)。
    all_dxdy = np.concatenate([s[:, :2] for s in raw_seqs], axis=0)
    dx_std = float(all_dxdy[:, 0].std()) or 1.0
    dy_std = float(all_dxdy[:, 1].std()) or 1.0
    for s in raw_seqs:
        s[:, 0] /= dx_std
        s[:, 1] /= dy_std

    vocab = sorted(set(chars_per_sample))
    char_to_id = {c: i for i, c in enumerate(vocab)}
    char_ids = [char_to_id[c] for c in chars_per_sample]

    return Dataset(sequences=raw_seqs, char_ids=char_ids, chars=vocab, dxdy_std=(dx_std, dy_std))

from __future__ import annotations

import torch

from .config import PEN_DOWN, PEN_END, PEN_UP, SampleConfig
from .mdn import sample_step
from .model import CharCondLSTMMDN

Stroke = list[tuple[float, float]]


@torch.no_grad()
def generate_strokes(
    model: CharCondLSTMMDN,
    char_id: int,
    dxdy_std: tuple[float, float],
    config: SampleConfig | None = None,
) -> list[Stroke]:
    """char_id 条件で自己回帰サンプリングし、セル正規化座標のストローク列を返す。"""
    config = config or SampleConfig()
    mixtures = model.config.mixtures
    std_x, std_y = dxdy_std
    cid = torch.tensor([char_id], dtype=torch.long)

    # 先頭入力: 移動なし・接地 (学習時の先頭トークンに一致)。
    x_t = torch.zeros(1, 1, 5)
    x_t[0, 0, 2 + PEN_DOWN] = 1.0
    state: tuple[torch.Tensor, torch.Tensor] | None = None

    cur_x = cur_y = 0.0
    strokes: list[Stroke] = []
    current: Stroke = [(0.0, 0.0)]

    for _ in range(config.max_len):
        raw, state = model.step(x_t, cid, state)
        dx_std, dy_std, pen = sample_step(raw[:, 0, :], mixtures, bias=config.bias)
        cur_x += dx_std * std_x
        cur_y += dy_std * std_y

        if pen == PEN_END:
            break
        if pen == PEN_UP:
            if len(current) >= 2:
                strokes.append(current)
            current = [(cur_x, cur_y)]
        else:  # PEN_DOWN
            current.append((cur_x, cur_y))

        x_t = torch.zeros(1, 1, 5)
        x_t[0, 0, 0] = dx_std
        x_t[0, 0, 1] = dy_std
        x_t[0, 0, 2 + pen] = 1.0

    if len(current) >= 2:
        strokes.append(current)
    return strokes

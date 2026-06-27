from __future__ import annotations

import math

import numpy as np
import torch

from lstm_mdn.config import PEN_DOWN, PEN_END, PEN_UP, ModelConfig
from lstm_mdn.data import _points_to_sequence, _resample_stroke
from lstm_mdn.mdn import mdn_loss
from lstm_mdn.model import CharCondLSTMMDN


def test_resample_is_uniform_arc_length():
    pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]  # 全長 2.0
    out = _resample_stroke(pts, step=0.5)
    assert len(out) == 5  # n = round(2.0/0.5) = 4 -> 5 点
    gaps = [math.dist(out[i], out[i + 1]) for i in range(len(out) - 1)]
    assert max(gaps) - min(gaps) < 1e-6


def test_sequence_pen_encoding():
    points = [(0.0, 0.0, 0), (0.5, 0.0, 0), (0.0, 1.0, 1), (0.5, 1.0, 1)]
    seq = _points_to_sequence(points)
    pen = seq[:, 2:5].argmax(axis=1)
    assert pen[0] == PEN_DOWN  # 先頭は接地
    assert pen[2] == PEN_UP  # stroke 境界は pen up
    assert pen[-1] == PEN_END  # 末尾は終了
    assert np.allclose(seq[0, :2], [0.0, 0.0])
    assert np.allclose(seq[-1, :2], [0.0, 0.0])


def test_mdn_loss_finite_and_overfits():
    torch.manual_seed(0)
    mixtures = 5
    model = CharCondLSTMMDN(3, ModelConfig(hidden=32, mixtures=mixtures, emb_dim=8))
    b, t = 4, 10
    x = torch.randn(b, t, 5) * 0.1
    dxdy = torch.randn(b, t, 2) * 0.1
    pen = torch.zeros(b, t, dtype=torch.long)
    mask = torch.ones(b, t)
    cids = torch.tensor([0, 1, 2, 0])
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)

    with torch.no_grad():
        first = float(mdn_loss(model(x, cids), dxdy, pen, mask, mixtures)[0])
    for _ in range(100):
        loss = mdn_loss(model(x, cids), dxdy, pen, mask, mixtures)[0]
        assert torch.isfinite(loss)
        opt.zero_grad()
        loss.backward()
        opt.step()
    with torch.no_grad():
        last = float(mdn_loss(model(x, cids), dxdy, pen, mask, mixtures)[0])
    assert last < first

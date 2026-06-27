from __future__ import annotations

import math

import torch
import torch.nn.functional as F

_EPS = 1e-6


def split_params(raw: torch.Tensor, mixtures: int) -> dict[str, torch.Tensor]:
    """MDN ヘッド出力 (..., M*6+3) を各パラメータへ分解する。"""
    m = mixtures
    pi_logits = raw[..., :m]
    mu = raw[..., m : 3 * m].reshape(*raw.shape[:-1], m, 2)
    log_sigma = raw[..., 3 * m : 5 * m].reshape(*raw.shape[:-1], m, 2)
    rho = torch.tanh(raw[..., 5 * m : 6 * m])
    pen_logits = raw[..., 6 * m :]
    sigma = torch.exp(log_sigma).clamp(min=_EPS)
    return {"pi_logits": pi_logits, "mu": mu, "sigma": sigma, "rho": rho, "pen_logits": pen_logits}


def _component_logprob(
    target: torch.Tensor,  # (..., 2)
    mu: torch.Tensor,  # (..., M, 2)
    sigma: torch.Tensor,  # (..., M, 2)
    rho: torch.Tensor,  # (..., M)
) -> torch.Tensor:
    t = target.unsqueeze(-2)  # (..., 1, 2)
    dx = (t[..., 0] - mu[..., 0]) / sigma[..., 0]
    dy = (t[..., 1] - mu[..., 1]) / sigma[..., 1]
    one_minus = (1.0 - rho * rho).clamp(min=_EPS)
    z = dx * dx + dy * dy - 2.0 * rho * dx * dy
    log_norm = (
        -torch.log(2.0 * math.pi * sigma[..., 0] * sigma[..., 1] * torch.sqrt(one_minus))
    )
    return log_norm - z / (2.0 * one_minus)  # (..., M)


def mdn_loss(
    raw: torch.Tensor,  # (B, T, M*6+3)
    target_dxdy: torch.Tensor,  # (B, T, 2)
    target_pen: torch.Tensor,  # (B, T) class idx
    mask: torch.Tensor,  # (B, T) bool/float
    mixtures: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    p = split_params(raw, mixtures)
    log_pi = F.log_softmax(p["pi_logits"], dim=-1)  # (B,T,M)
    comp = _component_logprob(target_dxdy, p["mu"], p["sigma"], p["rho"])  # (B,T,M)
    gauss_logprob = torch.logsumexp(log_pi + comp, dim=-1)  # (B,T)

    m = mask.float()
    denom = m.sum().clamp(min=1.0)
    gauss_nll = -(gauss_logprob * m).sum() / denom

    pen_ce = F.cross_entropy(
        p["pen_logits"].reshape(-1, p["pen_logits"].shape[-1]),
        target_pen.reshape(-1),
        reduction="none",
    ).reshape(target_pen.shape)
    pen_loss = (pen_ce * m).sum() / denom

    return gauss_nll + pen_loss, gauss_nll.detach(), pen_loss.detach()


@torch.no_grad()
def sample_step(raw_t: torch.Tensor, mixtures: int, *, bias: float) -> tuple[float, float, int]:
    """1 時刻分の MDN 出力 (1, M*6+3) から (dx, dy, pen) をサンプリングする。"""
    p = split_params(raw_t, mixtures)
    # Graves bias: pi を鋭く、sigma を縮める。
    pi = F.softmax(p["pi_logits"] * (1.0 + bias), dim=-1).squeeze(0)  # (M,)
    k = int(torch.multinomial(pi, 1).item())
    mu = p["mu"].squeeze(0)[k]  # (2,)
    sigma = p["sigma"].squeeze(0)[k] * math.exp(-bias)  # (2,)
    rho = float(p["rho"].squeeze(0)[k].item())

    z1 = torch.randn(()).item()
    z2 = torch.randn(()).item()
    sx, sy = float(sigma[0].item()), float(sigma[1].item())
    dx = float(mu[0].item()) + sx * z1
    dy = float(mu[1].item()) + sy * (rho * z1 + math.sqrt(max(1.0 - rho * rho, 0.0)) * z2)

    pen = int(torch.argmax(p["pen_logits"].squeeze(0)).item())
    return dx, dy, pen

from __future__ import annotations

import json
from pathlib import Path

import torch

from .config import ModelConfig
from .model import CharCondLSTMMDN


def save_checkpoint(
    checkpoint_path: Path,
    stats_path: Path,
    *,
    model: CharCondLSTMMDN,
    model_config: ModelConfig,
    chars: list[str],
    dxdy_std: tuple[float, float],
) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": model.state_dict(),
        "model_config": vars(model_config),
        "chars": chars,
        "dxdy_std": list(dxdy_std),
    }
    torch.save(payload, checkpoint_path)
    stats_path.write_text(
        json.dumps(
            {"chars": chars, "dxdy_std": list(dxdy_std), "model_config": vars(model_config)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_checkpoint(
    checkpoint_path: Path, map_location: str = "cpu"
) -> tuple[CharCondLSTMMDN, list[str], tuple[float, float], ModelConfig]:
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"checkpoint not found: {checkpoint_path} — まず hw-train で学習してください"
        )
    payload = torch.load(checkpoint_path, map_location=map_location, weights_only=False)
    model_config = ModelConfig(**payload["model_config"])
    model = CharCondLSTMMDN(num_chars=len(payload["chars"]), config=model_config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, payload["chars"], tuple(payload["dxdy_std"]), model_config

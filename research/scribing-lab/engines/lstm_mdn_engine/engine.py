"""runner 契約 generate(request) -> trajectory を満たす LSTM-MDN engine 入口。

学習済み checkpoint (data/checkpoint.pt) を読み、char 条件付きサンプリングで
各文字の筆跡を生成し、紙面 mm の canonical trajectory を返す。checkpoint が無い
場合は学習を促すエラーにする。
"""

from __future__ import annotations

import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# runner は engine.py をファイルパスで取り込むため、同梱パッケージを import 可能にする。
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

ENGINE_ID = "lstm-mdn-engine"

_MODEL_CACHE: dict[str, Any] = {}


@dataclass(frozen=True)
class EngineConfig:
    paper_width: float = 210.0
    paper_height: float = 297.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_size: float = 12.0
    char_spacing: float = 2.5
    line_height: float = 1.45
    advance_ratio: float = 0.9
    bias: float = 1.0
    draw_speed_mm_s: float = 32.0
    penup_speed_mm_s: float = 110.0


def generate(request: dict[str, Any]) -> dict[str, Any]:
    import torch

    from lstm_mdn import artifacts, sampler, trajectory
    from lstm_mdn.config import SampleConfig, resolve_checkpoint

    text = unicodedata.normalize("NFKC", str(request.get("text", "")))
    seed = int(request.get("seed", 1))
    params = dict(request.get("params", {}))
    config = _config_from_params(params)
    # params["checkpoint"] でモデルを選べる (パス or checkpoints/ 配下の名前)。既定は最新。
    checkpoint_path = resolve_checkpoint(params.get("checkpoint"))

    model, chars, dxdy_std, _ = _load_model(artifacts, checkpoint_path)
    char_to_id = {c: i for i, c in enumerate(chars)}
    sample_config = SampleConfig(bias=config.bias)

    torch.manual_seed(seed)

    points: list[dict] = []
    used: set[str] = set()
    missing: set[str] = set()
    x = config.margin_left
    y_top = config.paper_height - config.margin_top
    line_advance = config.char_size * config.line_height
    max_x = config.paper_width - config.margin_left
    t = 0.0
    cur_pos = (0.0, config.paper_height)

    for char in text:
        if char == "\n":
            x = config.margin_left
            y_top -= line_advance
            continue
        if char.isspace():
            x += config.char_size * 0.55
            continue
        cid = char_to_id.get(char)
        if cid is None:
            missing.add(char)
            x += config.char_size * config.advance_ratio + config.char_spacing
            continue
        if x + config.char_size > max_x:
            x = config.margin_left
            y_top -= line_advance

        strokes = sampler.generate_strokes(model, cid, dxdy_std, sample_config)
        strokes_mm = trajectory.map_to_paper(
            strokes, origin_x=x, top_y=y_top, size=config.char_size
        )
        t, cur_pos = trajectory.append_canonical(
            points,
            strokes_mm,
            t_start=t,
            last_pos=cur_pos,
            draw_speed_mm_s=config.draw_speed_mm_s,
            penup_speed_mm_s=config.penup_speed_mm_s,
        )
        used.add(char)
        x += config.char_size * config.advance_ratio + config.char_spacing

    return {
        "engine_id": ENGINE_ID,
        "engine_parameters": {
            "seed": seed,
            "config": config.__dict__,
            "params": params,
            "model": {
                "checkpoint": str(checkpoint_path),
                "vocab_size": len(chars),
                "used_chars": sorted(used),
                "missing_chars": sorted(missing),
            },
        },
        "trajectory": points,
    }


def _config_from_params(params: dict[str, Any]) -> EngineConfig:
    values = EngineConfig().__dict__.copy()
    for key, raw in params.items():
        if key in values:
            values[key] = float(raw)
    return EngineConfig(**values)


def _load_model(artifacts, checkpoint_path):
    key = str(checkpoint_path)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = artifacts.load_checkpoint(checkpoint_path)
    return _MODEL_CACHE[key]

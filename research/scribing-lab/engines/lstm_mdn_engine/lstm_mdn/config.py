from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ENGINE_DIR / "data"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.pt"
STATS_PATH = DATA_DIR / "stats.json"
DEFAULT_DATASET_GLOB = str(
    ENGINE_DIR.parents[1] / "handwriting-collector" / "datasets" / "*.jsonl"
)

# pen 状態 (Sketch-RNN / DESIGN §10.4 に準拠)
PEN_DOWN = 0  # 接地して描く
PEN_UP = 1  # ストローク間の移動 (非接地)
PEN_END = 2  # 文字終了
PEN_CLASSES = 3
INPUT_DIM = 2 + PEN_CLASSES  # (dx, dy, pen one-hot[3])


@dataclass(frozen=True)
class ModelConfig:
    emb_dim: int = 16
    hidden: int = 256
    layers: int = 1
    mixtures: int = 20
    dropout: float = 0.0


@dataclass(frozen=True)
class TrainConfig:
    resample_step: float = 0.05  # 正規化セル単位での弧長間隔
    batch_size: int = 32
    lr: float = 1e-3
    epochs: int = 400
    grad_clip: float = 5.0
    val_frac: float = 0.1
    seed: int = 1


@dataclass(frozen=True)
class SampleConfig:
    # Graves 2013 の bias。大きいほど混合の鋭さ・分散縮小で字形が安定する。
    bias: float = 1.0
    max_len: int = 300

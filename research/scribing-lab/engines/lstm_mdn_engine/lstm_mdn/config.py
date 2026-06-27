from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ENGINE_DIR / "data"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
# 旧来の固定パス (後方互換: 新規は checkpoints/ に日付・名前つきで出力する)。
CHECKPOINT_PATH = DATA_DIR / "checkpoint.pt"
STATS_PATH = DATA_DIR / "stats.json"
DEFAULT_DATASET_GLOB = str(
    ENGINE_DIR.parents[1] / "handwriting-collector" / "datasets" / "*.jsonl"
)


def _stats_path_for(checkpoint_path: Path) -> Path:
    return checkpoint_path.with_name(checkpoint_path.stem + ".stats.json")


def new_checkpoint_paths(name: str) -> tuple[Path, Path]:
    """`checkpoints/<YYYYMMDDTHHMMSS>_<name>.pt` と対応する stats パスを返す。"""
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "model"
    path = CHECKPOINTS_DIR / f"{stamp}_{safe}.pt"
    suffix = 2
    while path.exists():
        path = CHECKPOINTS_DIR / f"{stamp}_{safe}-{suffix:02d}.pt"
        suffix += 1
    return path, _stats_path_for(path)


def latest_checkpoint() -> Path | None:
    """最新の checkpoint を返す (checkpoints/ の名前降順、無ければ旧 checkpoint.pt)。"""
    if CHECKPOINTS_DIR.exists():
        found = sorted(CHECKPOINTS_DIR.glob("*.pt"))
        if found:
            return found[-1]
    return CHECKPOINT_PATH if CHECKPOINT_PATH.exists() else None


def resolve_checkpoint(spec: str | None) -> Path:
    """checkpoint 指定を解決する。

    spec が None なら最新。パスとして存在すればそれ。そうでなければ checkpoints/ 配下の
    名前 (拡張子省略可) として探す。
    """
    if not spec:
        latest = latest_checkpoint()
        if latest is None:
            raise FileNotFoundError("checkpoint が見つかりません。まず hw-train で学習してください")
        return latest
    direct = Path(spec)
    if direct.exists():
        return direct
    candidate = CHECKPOINTS_DIR / spec
    if candidate.exists():
        return candidate
    with_ext = CHECKPOINTS_DIR / (spec if spec.endswith(".pt") else f"{spec}.pt")
    if with_ext.exists():
        return with_ext
    raise FileNotFoundError(f"checkpoint not found: {spec}")

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
    epochs: int = 400  # 上限エポック
    grad_clip: float = 5.0
    val_frac: float = 0.1
    seed: int = 1
    patience: int = 40  # val が改善しないまま続いたら早期終了 (0 で無効)


@dataclass(frozen=True)
class SampleConfig:
    # Graves 2013 の bias。大きいほど混合の鋭さ・分散縮小で字形が安定する。
    bias: float = 1.0
    max_len: int = 300

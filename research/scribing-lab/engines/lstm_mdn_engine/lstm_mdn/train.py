from __future__ import annotations

import argparse
import random

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset as TorchDataset

from pathlib import Path

from . import artifacts
from .config import (
    DEFAULT_DATASET_GLOB,
    ModelConfig,
    TrainConfig,
    _stats_path_for,
    new_checkpoint_paths,
)
from .data import build_dataset
from .mdn import mdn_loss
from .model import CharCondLSTMMDN


class SeqDataset(TorchDataset):
    def __init__(self, sequences: list[np.ndarray], char_ids: list[int]) -> None:
        self.sequences = sequences
        self.char_ids = char_ids

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, i: int):
        return self.sequences[i], self.char_ids[i]


def collate(batch):
    lengths = [len(seq) - 1 for seq, _ in batch]
    max_t = max(lengths)
    b = len(batch)
    x = torch.zeros(b, max_t, 5)
    dxdy = torch.zeros(b, max_t, 2)
    pen = torch.zeros(b, max_t, dtype=torch.long)
    mask = torch.zeros(b, max_t)
    cids = torch.zeros(b, dtype=torch.long)
    for i, (seq, cid) in enumerate(batch):
        length = len(seq) - 1
        inp = torch.from_numpy(seq[:-1])
        tgt = seq[1:]
        x[i, :length] = inp
        dxdy[i, :length] = torch.from_numpy(tgt[:, :2])
        pen[i, :length] = torch.from_numpy(tgt[:, 2:5].argmax(axis=1).astype(np.int64))
        mask[i, :length] = 1.0
        cids[i] = cid
    return x, dxdy, pen, mask, torch.tensor(lengths), cids


def resolve_device(spec: str) -> torch.device:
    """device 指定を解決する。auto は cuda > mps > xpu > cpu の順で利用可能なものを選ぶ。"""
    if spec and spec != "auto":
        return torch.device(spec)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(getattr(torch.backends, "mps", None), "is_available", lambda: False)():
        return torch.device("mps")
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return torch.device("xpu")
    return torch.device("cpu")


def _run_epoch(model, loader, mixtures, device, optimizer=None, grad_clip=5.0):
    train = optimizer is not None
    model.train(train)
    total = 0.0
    count = 0
    for x, dxdy, pen, mask, lengths, cids in loader:
        x = x.to(device)
        dxdy = dxdy.to(device)
        pen = pen.to(device)
        mask = mask.to(device)
        cids = cids.to(device)
        # lengths は pack_padded_sequence のため CPU のまま (model 側で .cpu() 済み)。
        raw = model(x, cids, lengths)
        loss, _, _ = mdn_loss(raw, dxdy, pen, mask, mixtures)
        if train:
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
        total += float(loss.item())
        count += 1
    return total / max(count, 1)


def train(
    dataset_glob: str,
    model_config: ModelConfig,
    train_config: TrainConfig,
    checkpoint_path: Path,
    stats_path: Path,
    device: torch.device,
) -> None:
    random.seed(train_config.seed)
    np.random.seed(train_config.seed)
    torch.manual_seed(train_config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(train_config.seed)
    print(f"device={device}")

    data = build_dataset(dataset_glob, step=train_config.resample_step)
    print(f"samples={len(data.sequences)} chars={len(data.chars)} dxdy_std={data.dxdy_std}")

    indices = list(range(len(data.sequences)))
    random.shuffle(indices)
    n_val = max(1, int(len(indices) * train_config.val_frac))
    val_idx = set(indices[:n_val])
    train_set = SeqDataset(
        [data.sequences[i] for i in indices if i not in val_idx],
        [data.char_ids[i] for i in indices if i not in val_idx],
    )
    val_set = SeqDataset(
        [data.sequences[i] for i in indices if i in val_idx],
        [data.char_ids[i] for i in indices if i in val_idx],
    )
    train_loader = DataLoader(
        train_set, batch_size=train_config.batch_size, shuffle=True, collate_fn=collate
    )
    val_loader = DataLoader(val_set, batch_size=train_config.batch_size, collate_fn=collate)

    model = CharCondLSTMMDN(num_chars=len(data.chars), config=model_config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=train_config.lr)

    best_val = float("inf")
    best_epoch = 0
    no_improve = 0
    for epoch in range(1, train_config.epochs + 1):
        tr = _run_epoch(
            model, train_loader, model_config.mixtures, device, optimizer, train_config.grad_clip
        )
        with torch.no_grad():
            va = _run_epoch(model, val_loader, model_config.mixtures, device)
        if va < best_val:
            best_val = va
            best_epoch = epoch
            no_improve = 0
            artifacts.save_checkpoint(
                checkpoint_path,
                stats_path,
                model=model,
                model_config=model_config,
                chars=data.chars,
                dxdy_std=data.dxdy_std,
            )
        else:
            no_improve += 1
        if epoch % 10 == 0 or epoch == 1:
            print(f"epoch {epoch:4d}  train {tr:8.4f}  val {va:8.4f}  best {best_val:8.4f} (@{best_epoch})")
        if train_config.patience > 0 and no_improve >= train_config.patience:
            print(f"early stop @ epoch {epoch}: val が {train_config.patience} エポック改善せず")
            break

    print(f"done. best val {best_val:.4f} @ epoch {best_epoch} -> {checkpoint_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the char-conditioned LSTM-MDN kana engine.")
    parser.add_argument("--data", default=DEFAULT_DATASET_GLOB, help="dataset JSONL glob")
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=TrainConfig.batch_size)
    parser.add_argument("--lr", type=float, default=TrainConfig.lr)
    parser.add_argument("--hidden", type=int, default=ModelConfig.hidden)
    parser.add_argument("--mixtures", type=int, default=ModelConfig.mixtures)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    parser.add_argument(
        "--patience",
        type=int,
        default=TrainConfig.patience,
        help="val 非改善で早期終了するエポック数 (0 で無効)",
    )
    parser.add_argument("-n", "--name", default="model", help="checkpoint 名 (日付prefixが付く)")
    parser.add_argument("-o", "--out", type=Path, help="checkpoint 出力先を明示指定 (--name より優先)")
    parser.add_argument(
        "--device", default="auto", help="auto / cuda / mps / xpu / cpu (既定 auto)"
    )
    args = parser.parse_args()
    device = resolve_device(args.device)

    if args.out is not None:
        checkpoint_path, stats_path = args.out, _stats_path_for(args.out)
    else:
        checkpoint_path, stats_path = new_checkpoint_paths(args.name)

    model_config = ModelConfig(hidden=args.hidden, mixtures=args.mixtures)
    train_config = TrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        patience=args.patience,
    )
    train(args.data, model_config, train_config, checkpoint_path, stats_path, device)


if __name__ == "__main__":
    main()

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


def _run_epoch(model, loader, mixtures, optimizer=None, grad_clip=5.0):
    train = optimizer is not None
    model.train(train)
    total = 0.0
    count = 0
    for x, dxdy, pen, mask, lengths, cids in loader:
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
) -> None:
    random.seed(train_config.seed)
    np.random.seed(train_config.seed)
    torch.manual_seed(train_config.seed)

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

    model = CharCondLSTMMDN(num_chars=len(data.chars), config=model_config)
    optimizer = torch.optim.Adam(model.parameters(), lr=train_config.lr)

    best_val = float("inf")
    for epoch in range(1, train_config.epochs + 1):
        tr = _run_epoch(model, train_loader, model_config.mixtures, optimizer, train_config.grad_clip)
        with torch.no_grad():
            va = _run_epoch(model, val_loader, model_config.mixtures)
        if va < best_val:
            best_val = va
            artifacts.save_checkpoint(
                checkpoint_path,
                stats_path,
                model=model,
                model_config=model_config,
                chars=data.chars,
                dxdy_std=data.dxdy_std,
            )
        if epoch % 10 == 0 or epoch == 1:
            print(f"epoch {epoch:4d}  train {tr:8.4f}  val {va:8.4f}  best {best_val:8.4f}")

    print(f"done. best val {best_val:.4f} -> {checkpoint_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the char-conditioned LSTM-MDN kana engine.")
    parser.add_argument("--data", default=DEFAULT_DATASET_GLOB, help="dataset JSONL glob")
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=TrainConfig.batch_size)
    parser.add_argument("--lr", type=float, default=TrainConfig.lr)
    parser.add_argument("--hidden", type=int, default=ModelConfig.hidden)
    parser.add_argument("--mixtures", type=int, default=ModelConfig.mixtures)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    parser.add_argument("-n", "--name", default="model", help="checkpoint 名 (日付prefixが付く)")
    parser.add_argument("-o", "--out", type=Path, help="checkpoint 出力先を明示指定 (--name より優先)")
    args = parser.parse_args()

    if args.out is not None:
        checkpoint_path, stats_path = args.out, _stats_path_for(args.out)
    else:
        checkpoint_path, stats_path = new_checkpoint_paths(args.name)

    model_config = ModelConfig(hidden=args.hidden, mixtures=args.mixtures)
    train_config = TrainConfig(
        epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, seed=args.seed
    )
    train(args.data, model_config, train_config, checkpoint_path, stats_path)


if __name__ == "__main__":
    main()

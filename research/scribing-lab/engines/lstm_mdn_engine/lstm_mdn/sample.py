from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

import torch

from . import artifacts
from .config import DATA_DIR, SampleConfig, resolve_checkpoint
from .sampler import generate_strokes
from .trajectory import render_svg


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample handwriting from the trained engine.")
    parser.add_argument("--chars", default="あいうえお", help="生成する文字 (連結)")
    parser.add_argument("--count", type=int, default=5, help="各文字のサンプル数")
    parser.add_argument("--bias", type=float, default=SampleConfig.bias)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "-c", "--checkpoint", default=None, help="checkpoint パス/名前 (既定: 最新)"
    )
    parser.add_argument("--out", type=Path, default=DATA_DIR / "samples" / "samples.svg")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    model, chars, dxdy_std, _ = artifacts.load_checkpoint(resolve_checkpoint(args.checkpoint))
    char_to_id = {c: i for i, c in enumerate(chars)}
    config = SampleConfig(bias=args.bias)

    samples = []
    requested = [c for c in unicodedata.normalize("NFKC", args.chars) if not c.isspace()]
    for char in requested:
        cid = char_to_id.get(char)
        if cid is None:
            print(f"skip (not in vocab): {char!r}")
            continue
        for _ in range(args.count):
            samples.append(generate_strokes(model, cid, dxdy_std, config))

    if not samples:
        raise SystemExit("no samples generated (requested chars not in vocab)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_svg(samples, cols=args.count), encoding="utf-8")
    print(f"wrote {args.out} ({len(samples)} samples)")


if __name__ == "__main__":
    main()

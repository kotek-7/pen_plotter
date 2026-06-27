from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scribing_dataset_augment.augment import AugmentParams, augment_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Augment a JSONL handwriting dataset with small geometric variations."
    )
    parser.add_argument("input", type=Path, help="Input dataset (*.jsonl)")
    parser.add_argument("-o", "--output", type=Path, help="Output JSONL (default: <stem>.aug<N>x.jsonl)")
    parser.add_argument("-c", "--copies", type=int, default=4, help="Variations per sample")
    parser.add_argument("-s", "--seed", type=int, default=1)
    parser.add_argument("--rotate-deg", type=float, default=AugmentParams.rotate_deg)
    parser.add_argument("--scale", type=float, default=AugmentParams.scale)
    parser.add_argument("--shear", type=float, default=AugmentParams.shear)
    parser.add_argument("--jitter", type=float, default=AugmentParams.jitter)
    parser.add_argument(
        "--include-originals",
        action="store_true",
        help="出力に元サンプルも含める (既定は拡張分のみ)",
    )
    return parser


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def _write_jsonl(path: Path, samples: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for sample in samples:
            fh.write(json.dumps(sample, ensure_ascii=False) + "\n")


def main() -> None:
    args = build_parser().parse_args()
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    output = args.output or args.input.with_name(f"{args.input.stem}.aug{args.copies}x.jsonl")
    params = AugmentParams(
        rotate_deg=args.rotate_deg, scale=args.scale, shear=args.shear, jitter=args.jitter
    )

    samples = _read_jsonl(args.input)
    augmented = augment_dataset(
        samples,
        copies=args.copies,
        params=params,
        seed=args.seed,
        include_originals=args.include_originals,
    )
    _write_jsonl(output, augmented)
    print(f"input: {len(samples)} samples")
    print(f"wrote: {output} ({len(augmented)} samples, copies={args.copies})")


if __name__ == "__main__":
    main()

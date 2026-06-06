from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from writer_profile.public_datasets import download_and_convert_finnbusse_handwriting_v1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download and convert finnbusse/handwriting-v1 into canonical JSONL"
    )
    parser.add_argument("--output", required=True, help="Canonical JSONL output path")
    parser.add_argument(
        "--dataset-id",
        default="finnbusse/handwriting-v1",
        help="Hugging Face dataset id",
    )
    parser.add_argument(
        "--writer-id-mode",
        choices=("session_id", "file_stem"),
        default="session_id",
        help="How to derive writer_id for balanced aggregation",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="Download timeout in seconds")
    parser.add_argument(
        "--summary-output",
        default="",
        help="Optional path to write a JSON summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stats = download_and_convert_finnbusse_handwriting_v1(
        args.output,
        dataset_id=args.dataset_id,
        writer_id_mode=args.writer_id_mode,
        timeout=args.timeout,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if args.summary_output:
        Path(args.summary_output).write_text(
            json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

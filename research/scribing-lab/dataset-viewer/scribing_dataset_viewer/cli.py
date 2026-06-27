from __future__ import annotations

import argparse
from pathlib import Path

from scribing_dataset_viewer.viewer import ViewerConfig, default_datasets_dir, serve_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview JSONL handwriting datasets.")
    parser.add_argument(
        "datasets",
        nargs="?",
        type=Path,
        default=default_datasets_dir(),
        help="Datasets directory (contains *.jsonl)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=8766)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = ViewerConfig(
        datasets_dir=args.datasets.resolve(),
        host=args.host,
        port=args.port,
    )
    serve_viewer(config)


if __name__ == "__main__":
    main()

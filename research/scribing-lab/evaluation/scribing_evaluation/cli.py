from __future__ import annotations

import argparse
from pathlib import Path

from scribing_evaluation.viewer import ViewerConfig, default_runs_dir, serve_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View scribing run previews.")
    parser.add_argument("run", nargs="?", type=Path, help="Run directory to show")
    parser.add_argument("-r", "--runs", type=Path, default=default_runs_dir(), help="Runs directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run.resolve() if args.run else None
    runs_dir = run_dir.parent if run_dir else args.runs.resolve()
    config = ViewerConfig(
        runs_dir=runs_dir,
        run_dir=run_dir,
        host=args.host,
        port=args.port,
    )
    serve_viewer(config)


if __name__ == "__main__":
    main()

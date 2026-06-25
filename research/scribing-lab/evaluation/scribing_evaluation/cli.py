from __future__ import annotations

import argparse
from pathlib import Path

from scribing_evaluation.viewer import ViewerConfig, default_runs_dir, serve_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect scribing run outputs.")
    sub = parser.add_subparsers(dest="command", required=True)

    view = sub.add_parser("view", help="Open a local run preview viewer")
    view.add_argument("--runs-dir", type=Path, default=default_runs_dir())
    view.add_argument("--run", type=Path, help="Show one run directory")
    view.add_argument("--host", default="127.0.0.1")
    view.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "view":
        run_dir = args.run.resolve() if args.run else None
        runs_dir = run_dir.parent if run_dir else args.runs_dir.resolve()
        config = ViewerConfig(
            runs_dir=runs_dir,
            run_dir=run_dir,
            host=args.host,
            port=args.port,
        )
        serve_viewer(config)


if __name__ == "__main__":
    main()

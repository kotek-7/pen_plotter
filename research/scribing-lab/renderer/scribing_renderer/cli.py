from __future__ import annotations

import argparse
import json
from pathlib import Path

from scribing_renderer.svg import trajectory_to_svg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render preview.svg from a run's trajectory.json.")
    parser.add_argument("run", type=Path, help="Run directory containing trajectory.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run.resolve()
    trajectory_path = run_dir / "trajectory.json"
    if not trajectory_path.exists():
        raise SystemExit(f"trajectory.json not found: {trajectory_path}")

    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    preview_path = run_dir / "preview.svg"
    preview_path.write_text(trajectory_to_svg(trajectory), encoding="utf-8")
    print(f"preview: {preview_path}")


if __name__ == "__main__":
    main()

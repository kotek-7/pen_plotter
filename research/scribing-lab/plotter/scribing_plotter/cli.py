from __future__ import annotations

import argparse
import json
from pathlib import Path

from scribing_plotter.config import PlotterConfig
from scribing_plotter.gcode import trajectory_to_gcode
from scribing_plotter.safety import validate_gcode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate output.gcode and safety.json from a run's trajectory.json."
    )
    parser.add_argument("run", type=Path, help="Run directory containing trajectory.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run.resolve()
    trajectory_path = run_dir / "trajectory.json"
    if not trajectory_path.exists():
        raise SystemExit(f"trajectory.json not found: {trajectory_path}")

    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    config = PlotterConfig()
    gcode = trajectory_to_gcode(trajectory, config)
    safety = validate_gcode(gcode, config)

    gcode_path = run_dir / "output.gcode"
    safety_path = run_dir / "safety.json"
    gcode_path.write_text("\n".join(gcode) + "\n", encoding="utf-8")
    safety_path.write_text(
        json.dumps(safety, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"gcode: {gcode_path}")
    print(f"safety: {safety_path} (ok={safety['ok']})")


if __name__ == "__main__":
    main()

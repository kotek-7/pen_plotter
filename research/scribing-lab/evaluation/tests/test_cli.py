from __future__ import annotations

from scribing_evaluation.cli import build_parser
from scribing_evaluation.viewer import default_runs_dir


def test_cli_accepts_run_as_positional_argument() -> None:
    args = build_parser().parse_args(["../runs/example", "--port", "9000"])

    assert str(args.run) == "../runs/example"
    assert args.port == 9000


def test_cli_defaults_to_runs_directory() -> None:
    args = build_parser().parse_args([])

    assert args.run is None
    assert args.runs == default_runs_dir()

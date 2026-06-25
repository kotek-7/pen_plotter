from pathlib import Path

from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.cli import build_parser
from evaluation_harness.self_check import render_self_check_markdown, run_self_check


def test_self_check_runs_end_to_end(tmp_path: Path) -> None:
    result = run_self_check(tmp_path / "runs", seed=1)

    assert result.status == "ok"
    assert result.baseline_record_count == len(DEFAULT_EVALUATION_INPUTS)
    assert result.candidate_record_count == len(DEFAULT_EVALUATION_INPUTS)
    assert result.registry_record_count == len(DEFAULT_EVALUATION_INPUTS) * 2
    assert result.comparison["coverage_ratio"] == 1.0
    assert result.preview_comparison["preview_coverage_ratio"] == 1.0
    assert result.offline_review["robustness"]["status"] == "ok"
    assert result.human_review_summary["can_proceed_to_plot"] is True
    assert result.plot_ready_packet["plot_ready_count"] == result.human_review_packet[
        "representative_count"
    ]
    assert result.reference_basis["source_count"] >= 5
    assert result.reference_basis["axis_count"] >= 5
    assert any(source["name"] == "KanjiVG" for source in result.reference_basis["sources"])
    assert "too-font-like" in result.comparison["resolved_failure_tags"]
    assert "terminal-too-uniform" in result.comparison["resolved_failure_tags"]
    assert all(result.baseline_checks.values())
    assert all(result.candidate_checks.values())

    report = render_self_check_markdown(result)
    assert "# Evaluation Harness Self Check" in report
    assert "Reference Basis" in report
    assert "references" in report.lower()


def test_self_check_parser_accepts_outputs() -> None:
    args = build_parser().parse_args(
        [
            "self-check",
            "--root",
            "runs/test",
            "--seed",
            "2",
            "--output",
            "self_check.md",
            "--json-output",
            "self_check.json",
        ]
    )

    assert args.command == "self-check"
    assert args.root == "runs/test"
    assert args.seed == 2
    assert args.output == "self_check.md"
    assert args.json_output == "self_check.json"

from pathlib import Path

from evaluation_harness.cli import build_parser
from evaluation_harness.goal_audit import render_goal_audit_markdown, run_goal_audit


def test_goal_audit_runs_end_to_end(tmp_path: Path) -> None:
    result = run_goal_audit(tmp_path / "runs", seed=1)

    assert result.status == "ready_to_close"
    assert all(criterion.met for criterion in result.criteria)
    assert result.self_check["status"] == "ok"
    assert result.repeat_self_check["status"] == "ok"
    assert "ssim_proxy" in result.preview_comparison["preview_similarity_keys"]
    assert result.human_feedback_loop["response_summary"]["can_proceed_to_plot"] is True
    assert result.human_feedback_loop["calibration_summary"]["recommended_adjustments"]
    assert result.human_feedback_loop["agreement_summary"]["reviewer_count"] == 2
    assert result.human_feedback_loop["agreement_summary"]["mean_cohen_kappa"] is not None
    assert result.abx_summary["bradley_terry_ranking"][0] == "baseline"
    assert result.human_feedback_loop["next_actions"]

    report = render_goal_audit_markdown(result)
    assert "# Goal Audit" in report
    assert "ready_to_close" in report
    assert "self-check-repeatable" in report


def test_goal_audit_parser_accepts_outputs() -> None:
    args = build_parser().parse_args(
        [
            "goal-audit",
            "--root",
            "runs/test",
            "--seed",
            "2",
            "--output",
            "goal_audit.md",
            "--json-output",
            "goal_audit.json",
        ]
    )

    assert args.command == "goal-audit"
    assert args.root == "runs/test"
    assert args.seed == 2
    assert args.output == "goal_audit.md"
    assert args.json_output == "goal_audit.json"

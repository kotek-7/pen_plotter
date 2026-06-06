from pathlib import Path

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.revision_loop import (
    render_preview_revision_loop_markdown,
    render_preview_revision_loop_summary_markdown,
    run_preview_revision_loop_fixed_input_set,
    summarize_preview_revision_loops,
)
from evaluation_harness.writer_profile import build_revision_profile, resolve_writer_profile


def test_build_revision_profile_applies_motion_change() -> None:
    base_profile = resolve_writer_profile("baseline-neat")
    application = build_revision_profile(
        base_profile,
        [
            {
                "target": "motion",
                "parameter": "timing_jitter_cv",
                "direction": "increase",
                "amount_hint": 0.05,
                "reason": "increase motion variation",
            }
        ],
        revision_profile_id="baseline-neat-rev-001",
        created_from_experiment="exp-candidate",
    )

    profile = application["profile"]
    assert profile.profile_id == "baseline-neat-rev-001"
    assert profile.parent_profile == "baseline-neat"
    assert profile.created_from_experiment == "exp-candidate"
    assert profile.params.timing_jitter_cv == 0.13
    assert len(application["applied_changes"]) == 1
    assert application["unapplied_changes"] == []


def test_run_preview_revision_loop_fixed_input_set_reruns_selected_candidate(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )

    packet = run_preview_revision_loop_fixed_input_set(
        root,
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert packet["rerun_count"] == 1
    assert packet["applications"][0]["status"] == "rerun"
    assert packet["applications"][0]["revision_experiment_id"].startswith("exp-candidate-rev-")
    assert packet["comparison_summary"]["comparison_count"] == 1
    assert packet["design_principles"] == [
        "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
    ]
    assert packet["after_iteration"]["preview_group_summaries"][0]["candidate_count"] == 2
    report = render_preview_revision_loop_markdown(packet)
    assert "# Preview Revision Loop" in report
    assert "rerun_count" in report
    assert "design_principles" in report


def test_summarize_preview_revision_loops_collects_stable_principles() -> None:
    packets = [
        {
            "baseline_generator": "baseline-outline",
            "expected_input_texts": ["永"],
            "expected_seeds": [1],
            "rerun_count": 1,
            "coverage_delta": 0.0,
            "selected_candidate_delta": 0,
            "design_principles": [
                "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
            ],
            "comparison_summary": {
                "comparison_count": 1,
                "metric_names": ["draw_speed_cv"],
                "resolved_failure_tags": ["too-uniform"],
                "new_failure_tags": [],
            },
        },
        {
            "baseline_generator": "baseline-outline",
            "expected_input_texts": ["永"],
            "expected_seeds": [2],
            "rerun_count": 2,
            "coverage_delta": 0.1,
            "selected_candidate_delta": 1,
            "design_principles": [
                "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
                "layout: 長文が機械的なら baseline_drift_mm を増やす",
            ],
            "comparison_summary": {
                "comparison_count": 2,
                "metric_names": ["draw_speed_cv", "baseline_drift_mm"],
                "resolved_failure_tags": ["too-uniform", "line-too-mechanical"],
                "new_failure_tags": [],
            },
        },
    ]

    summary = summarize_preview_revision_loops(packets)

    assert summary["packet_count"] == 2
    assert summary["rerun_count_total"] == 3
    assert summary["stable_design_principles"] == [
        "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
    ]
    assert summary["recurring_design_principles"] == [
        "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
    ]
    report = render_preview_revision_loop_summary_markdown(summary)
    assert "# Preview Revision Loop Summary" in report
    assert "stable_design_principles" in report


def _record(
    *,
    experiment_id: str,
    input_text: str,
    seed: int,
    generator: str,
    artifacts: dict[str, str] | None = None,
    metrics: dict[str, float | int | str] | None = None,
    failure_tags: list[str] | None = None,
) -> ExperimentRecord:
    resolved_artifacts = dict(artifacts or {})
    resolved_artifacts.setdefault("report", f"artifacts/{experiment_id}/report.md")
    resolved_metrics = dict(metrics or {})
    resolved_metrics.setdefault("duration_ms", 1000)
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts=resolved_artifacts,
        metrics=resolved_metrics,
        failure_tags=failure_tags or [],
        next_action="review",
    )

from pathlib import Path

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.revision_loop import (
    evaluate_data_driven_writer_prior_fixed_input_set,
    evaluate_stable_writer_profile_candidates,
    render_preview_revision_loop_markdown,
    render_preview_revision_loop_summary_markdown,
    render_data_driven_writer_prior_evaluation_markdown,
    render_stable_writer_profile_evaluation_markdown,
    render_stable_writer_profile_candidates_markdown,
    propose_stable_writer_profile_candidates,
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


def test_propose_stable_writer_profile_candidates_builds_bundle() -> None:
    summary = {
        "packet_count": 2,
        "stable_design_principles": [
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
        ],
        "recurring_design_principles": [
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
            "layout: 長文が機械的なら baseline_drift_mm を増やす",
        ],
        "design_principle_counts": {
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる": 2,
            "layout: 長文が機械的なら baseline_drift_mm を増やす": 2,
        },
    }

    bundle = propose_stable_writer_profile_candidates(summary, base_profile_id="baseline-neat")

    assert bundle["base_profile_id"] == "baseline-neat"
    assert len(bundle["candidates"]) == 2
    assert bundle["candidates"][0]["candidate_type"] == "stable"
    assert bundle["candidates"][0]["profile"]["parent_profile"] == "baseline-neat"
    assert bundle["candidates"][0]["applied_changes"][0]["parameter"] == "timing_jitter_cv"
    report = render_stable_writer_profile_candidates_markdown(bundle)
    assert "# Stable Writer Profile Candidates" in report
    assert "candidate_count" not in report


def test_evaluate_stable_writer_profile_candidates_selects_stable_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "runs"
    summary = {
        "packet_count": 2,
        "stable_design_principles": [
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
        ],
        "recurring_design_principles": [
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
            "layout: 長文が機械的なら baseline_drift_mm を増やす",
        ],
        "design_principle_counts": {
            "motion: 等速感が強いときは timing_jitter_cv を先に上げる": 2,
            "layout: 長文が機械的なら baseline_drift_mm を増やす": 2,
        },
    }

    def fake_run_structure_motion(
        *,
        root: Path,
        experiment_id: str,
        input_text: str,
        seed: int,
        writer_profile,
        **_: object,
    ) -> ExperimentRecord:
        params = writer_profile.params
        is_baseline = writer_profile.profile_id == "baseline-neat"
        failure_tags = ["too-uniform"] if is_baseline else []
        if params.baseline_drift_mm > 0:
            failure_tags.append("line-too-mechanical")
        metrics = {
            "duration_ms": 1000,
            "velocity_peak_count": 0 if is_baseline else 3,
            "draw_speed_cv": 0.01 if is_baseline else 0.2,
            "baseline_drift_mm": params.baseline_drift_mm,
            "gcode_safety_ok": 1,
            "gcode_safety_violation_count": 0,
        }
        return _record(
            experiment_id=experiment_id,
            input_text=input_text,
            seed=seed,
            generator="structure-motion",
            profile_id=writer_profile.profile_id,
            metrics=metrics,
            failure_tags=failure_tags,
            artifacts={
                "preview": str(root / f"{experiment_id}.png"),
                "report": str(root / f"{experiment_id}.md"),
            },
        )

    monkeypatch.setattr(
        "evaluation_harness.revision_loop.run_structure_motion",
        fake_run_structure_motion,
    )

    packet = evaluate_stable_writer_profile_candidates(
        root,
        summary,
        expected_input_texts=("永",),
        expected_seeds=(1, 2),
    )

    assert packet["candidate_count"] == 2
    assert packet["selected_profile_count"] == 1
    assert packet["selected_profile_ids"] == [packet["selected_candidates"][0]["profile"]["profile_id"]]
    assert packet["selection_summary"]["selection_status"] == "partial"
    assert packet["selection_summary"]["selected_candidate_count"] == 1
    assert packet["candidate_evaluations"][0]["selected"] is True
    assert packet["candidate_evaluations"][0]["evaluation"]["resolved_failure_tag_count"] == 2
    assert packet["candidate_evaluations"][1]["selected"] is False
    assert packet["candidate_evaluations"][1]["evaluation"]["new_failure_tag_count"] > 0
    report = render_stable_writer_profile_evaluation_markdown(packet)
    assert "# Stable Writer Profile Evaluation" in report
    assert "selected_profile_ids" in report


def test_evaluate_data_driven_writer_prior_fixed_input_set_selects_derived_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "runs"
    samples_path = tmp_path / "samples.jsonl"
    samples_path.write_text(
        "\n".join(
            [
                _point_line("sample-1", "writer-a", "永", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 1.0, 1.0, 10, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 2.0, 2.0, 20, 1, 1.2),
                _point_line("sample-1", "writer-a", "永", 2.5, 2.2, 30, 0, None),
                _point_line("sample-2", "writer-b", "あ", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 0.5, 1.0, 20, 1, 1.1),
                _point_line("sample-2", "writer-b", "あ", 1.5, 2.5, 40, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 2.0, 3.0, 50, 0, None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_run_structure_motion(
        *,
        root: Path,
        experiment_id: str,
        input_text: str,
        seed: int,
        writer_profile,
        **_: object,
    ) -> ExperimentRecord:
        is_baseline = writer_profile.profile_id == "baseline-neat"
        failure_tags = ["too-uniform"] if is_baseline else []
        metrics = {
            "duration_ms": 1000,
            "velocity_peak_count": 0 if is_baseline else 3,
            "draw_speed_cv": 0.01 if is_baseline else 0.2,
            "baseline_drift_mm": 0.0 if is_baseline else 0.4,
            "shape_variation_mm": 0.0 if is_baseline else 0.5,
            "layout_variation_mm": 0.0 if is_baseline else 0.5,
            "gcode_safety_ok": 1,
            "gcode_safety_violation_count": 0,
        }
        return _record(
            experiment_id=experiment_id,
            input_text=input_text,
            seed=seed,
            generator="structure-motion",
            profile_id=writer_profile.profile_id,
            metrics=metrics,
            failure_tags=failure_tags,
            artifacts={
                "preview": str(root / f"{experiment_id}.png"),
                "report": str(root / f"{experiment_id}.md"),
            },
        )

    monkeypatch.setattr(
        "evaluation_harness.revision_loop.run_structure_motion",
        fake_run_structure_motion,
    )

    packet = evaluate_data_driven_writer_prior_fixed_input_set(
        root,
        samples_jsonl=samples_path,
        expected_input_texts=("永",),
        expected_seeds=(1, 2),
    )

    assert packet["selected"] is True
    assert packet["selected_profile_id"].startswith("baseline-neat-data-prior-")
    assert packet["evaluation_summary"]["selection_status"] == "selected"
    assert packet["comparison"]["resolved_failure_tag_count"] == 2
    assert packet["comparison"]["new_failure_tag_count"] == 0
    report = render_data_driven_writer_prior_evaluation_markdown(packet)
    assert "# Data-driven Writer Prior Evaluation" in report
    assert "selected_profile_id" in report


def _point_line(
    sample_id: str,
    writer_id: str,
    char_or_text: str,
    x_mm: float,
    y_mm: float,
    t_ms: int,
    pen_state: int,
    pressure_optional: float | None,
) -> str:
    return (
        "{"
        f"\"sample_id\": \"{sample_id}\", "
        f"\"writer_id\": \"{writer_id}\", "
        f"\"char_or_text\": \"{char_or_text}\", "
        f"\"x_mm\": {x_mm}, "
        f"\"y_mm\": {y_mm}, "
        f"\"t_ms\": {t_ms}, "
        f"\"pen_state\": {pen_state}, "
        f"\"pressure_optional\": {json_value(pressure_optional)}, "
        "\"source\": \"stylus\", "
        "\"license_scope\": \"research-only\""
        "}"
    )


def json_value(value: float | None) -> str:
    if value is None:
        return "null"
    return str(value)


def _record(
    *,
    experiment_id: str,
    input_text: str,
    seed: int,
    generator: str,
    profile_id: str = "baseline-neat",
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
        profile_id=profile_id,
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts=resolved_artifacts,
        metrics=resolved_metrics,
        failure_tags=failure_tags or [],
        next_action="review",
    )

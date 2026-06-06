from pathlib import Path

from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.compare import (
    compare_against_baseline,
    compare_fixed_input_set,
    compare_preview_fixed_input_set,
    recommend_preview_fixed_input_set,
    propose_preview_fixed_input_set,
    preview_iteration_fixed_input_set,
    render_comparison_markdown,
    render_fixed_input_comparison_markdown,
    render_preview_fixed_input_comparison_markdown,
    render_preview_iteration_markdown,
    render_preview_recommendation_markdown,
    render_preview_revision_plan_markdown,
)
from evaluation_harness.models import ExperimentRecord


def test_compare_against_baseline_reports_metric_deltas() -> None:
    baseline = ExperimentRecord(
        experiment_id="exp-baseline",
        hypothesis="baseline",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="baseline-outline",
        exporter="xdraw-gcode",
        metrics={"duration_ms": 1000, "draw_speed_cv": 0.0},
        failure_tags=["too-font-like", "terminal-too-uniform"],
    )
    candidate = ExperimentRecord(
        experiment_id="exp-candidate",
        hypothesis="candidate",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="structure-uniform",
        exporter="xdraw-gcode",
        metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
        failure_tags=["terminal-too-uniform"],
    )

    comparison = compare_against_baseline([baseline, candidate])

    assert comparison["comparison_count"] == 1
    item = comparison["comparisons"][0]
    assert item["metric_deltas"]["duration_ms"] == -100.0
    assert item["metric_deltas"]["draw_speed_cv"] == 0.2
    assert item["resolved_failure_tags"] == ["too-font-like"]


def test_render_comparison_markdown_handles_no_candidates() -> None:
    baseline = ExperimentRecord(
        experiment_id="exp-baseline",
        hypothesis="baseline",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="baseline-outline",
        exporter="xdraw-gcode",
    )

    report = render_comparison_markdown(compare_against_baseline([baseline]))

    assert "# Baseline Comparison Report" in report
    assert "- none" in report


def test_compare_fixed_input_set_reports_complete_coverage() -> None:
    records = [
        _record(
            experiment_id=f"exp-baseline-{index}-{seed}",
            input_text=input_text,
            seed=seed,
            generator="baseline-outline",
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS[:2], start=1)
        for seed in (1, 2)
    ]
    records.extend(
        _record(
            experiment_id=f"exp-candidate-{index}-{seed}",
            input_text=input_text,
            seed=seed,
            generator="structure-uniform",
            metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
            failure_tags=["terminal-too-uniform"],
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS[:2], start=1)
        for seed in (1, 2)
    )

    comparison = compare_fixed_input_set(
        records,
        expected_input_texts=DEFAULT_EVALUATION_INPUTS[:2],
        expected_seeds=(1, 2),
    )

    assert comparison["expected_group_count"] == 4
    assert comparison["complete_group_count"] == 4
    assert comparison["coverage_ratio"] == 1.0
    assert all(item["status"] == "complete" for item in comparison["group_summaries"])
    report = render_fixed_input_comparison_markdown(comparison)
    assert "# Fixed Input Comparison Report" in report
    assert "coverage_ratio" in report


def test_compare_fixed_input_set_reports_missing_baselines() -> None:
    comparison = compare_fixed_input_set(
        [
            _record(
                experiment_id="exp-candidate",
                input_text="永",
                seed=1,
                generator="structure-uniform",
                metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
            )
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert comparison["complete_group_count"] == 0
    assert comparison["coverage_ratio"] == 0.0
    assert comparison["group_summaries"][0]["status"] == "missing-baseline"


def test_compare_preview_fixed_input_set_reports_preview_hash_deltas(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    candidate_preview = tmp_path / "candidate.png"
    baseline_preview.write_bytes(b"baseline-preview")
    candidate_preview.write_bytes(b"candidate-preview")

    records = [
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        ),
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            artifacts={"preview": str(candidate_preview)},
        ),
    ]

    comparison = compare_preview_fixed_input_set(
        records,
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert comparison["expected_group_count"] == 1
    assert comparison["preview_ready_count"] == 1
    assert comparison["preview_hash_changed_count"] == 1
    assert comparison["preview_group_summaries"][0]["preview_comparison_count"] == 1
    assert comparison["preview_comparisons"][0]["preview_hash_changed"] is True
    report = render_preview_fixed_input_comparison_markdown(comparison)
    assert "# Preview Comparison Report" in report
    assert "preview_hash_changed" in report


def test_compare_preview_fixed_input_set_reports_missing_preview(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    baseline_preview.write_bytes(b"baseline-preview")

    comparison = compare_preview_fixed_input_set(
        [
            _record(
                experiment_id="exp-baseline",
                input_text="永",
                seed=1,
                generator="baseline-outline",
                artifacts={"preview": str(baseline_preview)},
            ),
            _record(
                experiment_id="exp-candidate",
                input_text="永",
                seed=1,
                generator="structure-motion",
                artifacts={},
            ),
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert comparison["preview_ready_count"] == 0
    assert comparison["preview_comparisons"][0]["preview_comparable"] is False


def test_recommend_preview_fixed_input_set_selects_lowest_failure_candidate(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    good_preview = tmp_path / "good.png"
    bad_preview = tmp_path / "bad.png"
    baseline_preview.write_bytes(b"baseline-preview")
    good_preview.write_bytes(b"good-preview")
    bad_preview.write_bytes(b"bad-preview")

    records = [
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        ),
        _record(
            experiment_id="exp-good",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "velocity_peak_count": 3,
                "draw_speed_cv": 0.2,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(good_preview)},
        ),
        _record(
            experiment_id="exp-bad",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={"velocity_peak_count": 0, "draw_speed_cv": 0.01},
            artifacts={"preview": str(bad_preview)},
        ),
    ]

    recommendation = recommend_preview_fixed_input_set(
        records,
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    selected = recommendation["recommendations"][0]["selected_candidate"]
    assert selected["experiment_id"] == "exp-good"
    assert recommendation["selected_candidate_count"] == 1
    assert recommendation["selected_coverage_ratio"] == 1.0
    assert recommendation["recommended_action_counts"][
        "preview を基準に次の profile 比較を行う"
    ] == 1
    assert "exp-good" in render_preview_recommendation_markdown(recommendation)


def test_recommend_preview_fixed_input_set_reports_action_from_tags(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    candidate_preview = tmp_path / "candidate.png"
    baseline_preview.write_bytes(b"baseline-preview")
    candidate_preview.write_bytes(b"candidate-preview")

    recommendation = recommend_preview_fixed_input_set(
        [
            _record(
                experiment_id="exp-baseline",
                input_text="永",
                seed=1,
                generator="baseline-outline",
                artifacts={"preview": str(baseline_preview)},
            ),
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
            ),
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    selected = recommendation["recommendations"][0]["selected_candidate"]
    assert selected["inferred_failure_tags"] == ["too-uniform"]
    assert selected["suggested_next_actions"] == [
        "motion-synthesis の speed profile / timing jitter を上げる"
    ]


def test_propose_preview_fixed_input_set_builds_revision_plan(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    candidate_preview = tmp_path / "candidate.png"
    baseline_preview.write_bytes(b"baseline-preview")
    candidate_preview.write_bytes(b"candidate-preview")

    proposal = propose_preview_fixed_input_set(
        [
            _record(
                experiment_id="exp-baseline",
                input_text="永",
                seed=1,
                generator="baseline-outline",
                artifacts={"preview": str(baseline_preview)},
            ),
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
            ),
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    plan = proposal["revision_plans"][0]
    assert plan["focus_area"] == "motion"
    assert plan["proposed_changes"][0]["target"] == "motion"
    assert plan["proposed_changes"][0]["parameter"] == "timing_jitter_cv"
    assert "再生成" in plan["next_experiment_hint"]
    report = render_preview_revision_plan_markdown(proposal)
    assert "# Preview Revision Plan" in report
    assert "selected_candidate_count" in report


def test_preview_iteration_fixed_input_set_reports_iteration_status(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    candidate_preview = tmp_path / "candidate.png"
    baseline_preview.write_bytes(b"baseline-preview")
    candidate_preview.write_bytes(b"candidate-preview")

    iteration = preview_iteration_fixed_input_set(
        [
            _record(
                experiment_id="exp-baseline",
                input_text="永",
                seed=1,
                generator="baseline-outline",
                artifacts={"preview": str(baseline_preview)},
            ),
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
            ),
        ],
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert iteration["iteration_status"] == "ready"
    assert iteration["iteration_selected_area_count"] == 1
    assert iteration["iteration_next_experiment_hints"] == [
        "同じ input / seed で motion profile を上げて再生成する"
    ]
    report = render_preview_iteration_markdown(iteration)
    assert "# Preview Iteration Report" in report
    assert "iteration_status" in report


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
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts=artifacts or {},
        metrics=metrics or {},
        failure_tags=failure_tags or [],
    )

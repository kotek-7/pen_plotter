from pathlib import Path

from evaluation_harness.human_abx import build_human_abx_packet, render_human_abx_packet_markdown
from evaluation_harness.models import ExperimentRecord


def test_build_human_abx_packet_prefers_selected_profile_counts(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    fast_preview = tmp_path / "fast.png"
    baseline_preview.write_bytes(b"baseline")
    fast_preview.write_bytes(b"fast")

    records = [
        _record(
            "exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        ),
        _record(
            "exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            profile_id="fast-casual",
            artifacts={"preview": str(fast_preview)},
            metrics={
                "draw_speed_cv": 0.56,
                "baseline_drift_mm": 4.02,
                "penup_distance_mm": 12.0,
                "visible_char_count": 1,
            },
        ),
    ]

    packet = build_human_abx_packet(
        records,
        expected_input_texts=("永",),
        expected_seeds=(1,),
    )

    assert packet["selected_candidate_count"] == 1
    assert packet["selected_profile_counts"] == {"fast-casual": 1}
    assert packet["candidate_profile_counts"] == {"fast-casual": 1}
    assert packet["abx_items"][0]["expected_preference"] == "B"
    assert packet["abx_items"][0]["option_a_artifact"].endswith("baseline.png")
    assert packet["abx_items"][0]["option_b_artifact"].endswith("fast.png")
    report = render_human_abx_packet_markdown(packet)
    assert "# Human ABX Packet" in report
    assert "selected_profile_counts" in report


def test_build_human_abx_packet_can_reuse_recommendation(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    fast_preview = tmp_path / "fast.png"
    baseline_preview.write_bytes(b"baseline")
    fast_preview.write_bytes(b"fast")

    recommendation = {
        "baseline_generator": "baseline-outline",
        "expected_input_texts": ["永"],
        "expected_seeds": [1],
        "expected_group_count": 1,
        "selected_candidate_count": 1,
        "selected_coverage_ratio": 1.0,
        "selected_profile_counts": {"fast-casual": 1},
        "candidate_profile_counts": {"fast-casual": 1},
        "focus_area_counts": {"preview": 1},
        "recommended_action_counts": {"preview を基準に次の profile 比較を行う": 1},
        "preview_comparisons": [
            {
                "input_text": "永",
                "seed": 1,
                "baseline_experiment_id": "exp-baseline",
                "baseline_preview": {"path": str(baseline_preview)},
                "candidate_experiment_id": "exp-candidate",
                "candidate_preview": {"path": str(fast_preview)},
                "preview_comparable": True,
                "preview_hash_changed": True,
                "preview_similarity": {"score": 1.0},
                "preview_size_delta": 0,
            }
        ],
        "recommendations": [
            {
                "input_text": "永",
                "seed": 1,
                "baseline_experiment_id": "exp-baseline",
                "selection_status": "selected",
                "selected_candidate": {
                    "experiment_id": "exp-candidate",
                    "profile_id": "fast-casual",
                    "preview": {"path": str(fast_preview)},
                    "inferred_failure_tags": [],
                    "suggested_next_actions": [],
                },
                "candidate_count": 1,
                "preview_candidate_count": 1,
                "candidate_items": [],
            }
        ],
    }

    packet = build_human_abx_packet(recommendation=recommendation)

    assert packet["record_count"] == 2
    assert packet["baseline_generator"] == "baseline-outline"
    assert packet["expected_input_texts"] == ["永"]
    assert packet["expected_seeds"] == [1]
    assert packet["selected_candidate_count"] == 1
    assert packet["selected_profile_counts"] == {"fast-casual": 1}
    assert packet["abx_items"][0]["option_a_artifact"].endswith("baseline.png")
    assert packet["abx_items"][0]["option_b_artifact"].endswith("fast.png")


def _record(
    experiment_id: str,
    *,
    input_text: str,
    seed: int,
    generator: str,
    profile_id: str = "baseline-neat",
    artifacts: dict[str, str] | None = None,
    metrics: dict[str, float | int | str] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id=profile_id,
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts=artifacts or {},
        metrics=metrics or {},
    )

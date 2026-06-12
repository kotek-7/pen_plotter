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

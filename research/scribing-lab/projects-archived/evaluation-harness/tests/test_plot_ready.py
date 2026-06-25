import pytest

from evaluation_harness.models import ExperimentRecord
from evaluation_harness.plot_ready import build_plot_ready_packet, render_plot_ready_packet_markdown


def test_build_plot_ready_packet_collects_safe_accepted_records() -> None:
    record = _record("exp-a")
    summary = _summary(["exp-a"])

    packet = build_plot_ready_packet([record], summary)

    assert packet["plot_ready_count"] == 1
    assert packet["safety_ok_count"] == 1
    assert packet["items"][0]["gcode"].endswith("output.gcode")


def test_build_plot_ready_packet_rejects_unaccepted_summary() -> None:
    with pytest.raises(ValueError, match="not accepted"):
        build_plot_ready_packet([_record("exp-a")], {**_summary(["exp-a"]), "can_proceed_to_plot": False})


def test_build_plot_ready_packet_rejects_unsafe_record() -> None:
    record = _record("exp-a", safety_ok=0)

    with pytest.raises(ValueError, match="not plot safe"):
        build_plot_ready_packet([record], _summary(["exp-a"]))


def test_build_plot_ready_packet_rejects_missing_artifacts() -> None:
    record = _record("exp-a", artifacts={"preview": "preview.png"})

    with pytest.raises(ValueError, match="missing plot-ready artifacts"):
        build_plot_ready_packet([record], _summary(["exp-a"]))


def test_render_plot_ready_packet_markdown_includes_checklist() -> None:
    packet = build_plot_ready_packet([_record("exp-a")], _summary(["exp-a"]))

    report = render_plot_ready_packet_markdown(packet)

    assert "# Plot Ready Packet" in report
    assert "Do not auto-send" in report
    assert "followup_audit_target" in report


def _record(
    experiment_id: str,
    *,
    safety_ok: int = 1,
    artifacts: dict[str, str] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text="永",
        profile_id="baseline-neat",
        seed=1,
        generator="structure-motion",
        exporter="xdraw-gcode",
        artifacts=artifacts
        or {
            "gcode": f"artifacts/{experiment_id}/output.gcode",
            "gcode_safety": f"artifacts/{experiment_id}/gcode_safety.json",
            "preview": f"artifacts/{experiment_id}/preview.png",
        },
        metrics={
            "gcode_safety_ok": safety_ok,
            "gcode_safety_violation_count": 0 if safety_ok else 1,
            "gcode_line_count": 100,
        },
    )


def _summary(experiment_ids: list[str]) -> dict[str, object]:
    return {
        "can_proceed_to_plot": True,
        "response_count": len(experiment_ids),
        "responses": [
            {
                "experiment_id": experiment_id,
                "decision": "accept",
                "reason_tags": [],
                "notes": "",
                "reviewer_id": "reviewer-test",
            }
            for experiment_id in experiment_ids
        ],
    }

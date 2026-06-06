from __future__ import annotations

from typing import Any

from evaluation_harness.models import ExperimentRecord


def build_plot_ready_packet(
    records: list[ExperimentRecord],
    human_review_summary: dict[str, Any],
) -> dict[str, Any]:
    if not bool(human_review_summary.get("can_proceed_to_plot", False)):
        raise ValueError("human review summary is not accepted for plotting")

    by_id = {record.experiment_id: record for record in records}
    accepted_ids = [
        str(response["experiment_id"])
        for response in human_review_summary.get("responses", [])
        if response.get("decision") == "accept"
    ]
    missing_ids = sorted(set(accepted_ids) - set(by_id))
    if missing_ids:
        raise ValueError(f"accepted experiment ids are missing from registry: {missing_ids}")

    items = [_plot_ready_item(by_id[experiment_id]) for experiment_id in accepted_ids]
    unsafe = [
        item["experiment_id"]
        for item in items
        if not item["safety_ok"] or item["safety_violation_count"] != 0
    ]
    if unsafe:
        raise ValueError(f"accepted experiments are not plot safe: {unsafe}")

    return {
        "plot_ready_count": len(items),
        "source_response_count": int(human_review_summary.get("response_count", 0)),
        "accepted_experiment_ids": accepted_ids,
        "safety_ok_count": sum(1 for item in items if item["safety_ok"]),
        "items": items,
        "preplot_checklist": _preplot_checklist(),
    }


def render_plot_ready_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Plot Ready Packet",
        "",
        f"- plot_ready_count: `{packet['plot_ready_count']}`",
        f"- source_response_count: `{packet['source_response_count']}`",
        f"- safety_ok_count: `{packet['safety_ok_count']}`",
        "",
        "## Preplot Checklist",
        "",
    ]
    lines.extend(f"- {item}" for item in packet["preplot_checklist"])
    lines.extend(["", "## Plot Targets", ""])
    if not packet["items"]:
        lines.append("- none")
    for item in packet["items"]:
        lines.extend(
            [
                f"### {item['experiment_id']}",
                "",
                f"- input_text: `{item['input_text']}`",
                f"- seed: `{item['seed']}`",
                f"- gcode: `{item['gcode']}`",
                f"- gcode_safety: `{item['gcode_safety']}`",
                f"- preview: `{item['preview']}`",
                f"- safety_ok: `{item['safety_ok']}`",
                f"- safety_violation_count: `{item['safety_violation_count']}`",
                f"- followup_audit_target: `{item['experiment_id']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _plot_ready_item(record: ExperimentRecord) -> dict[str, Any]:
    missing = [
        name
        for name in ("gcode", "gcode_safety", "preview")
        if name not in record.artifacts
    ]
    if missing:
        raise ValueError(f"missing plot-ready artifacts for {record.experiment_id}: {missing}")

    return {
        "experiment_id": record.experiment_id,
        "input_text": record.input_text,
        "seed": record.seed,
        "gcode": record.artifacts["gcode"],
        "gcode_safety": record.artifacts["gcode_safety"],
        "preview": record.artifacts["preview"],
        "safety_ok": int(record.metrics.get("gcode_safety_ok", 0)) == 1,
        "safety_violation_count": int(record.metrics.get("gcode_safety_violation_count", 0)),
        "gcode_line_count": int(record.metrics.get("gcode_line_count", 0)),
    }


def _preplot_checklist() -> list[str]:
    return [
        "Do not auto-send G-code from this packet.",
        "Confirm xDraw A4 is homed before plotting.",
        "Confirm paper coordinates are set with G92 X0 Y297 Z0.",
        "Confirm pen control uses Z axis, not M3/M5.",
        "Confirm gcode_safety has ok=true and violations=[] for each target.",
        "Use the experiment_id as the follow-up audit target after plotting if a scan is needed.",
    ]

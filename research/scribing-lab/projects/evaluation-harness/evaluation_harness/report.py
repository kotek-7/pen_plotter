from __future__ import annotations

from evaluation_harness.models import ExperimentRecord


def render_markdown_report(record: ExperimentRecord) -> str:
    lines = [
        f"# Experiment {record.experiment_id}",
        "",
        "## Hypothesis",
        "",
        record.hypothesis,
        "",
        "## Configuration",
        "",
        f"- input_text: `{record.input_text}`",
        f"- profile_id: `{record.profile_id}`",
        f"- seed: `{record.seed}`",
        f"- generator: `{record.generator}`",
        f"- exporter: `{record.exporter}`",
        "",
        "## Artifacts",
        "",
    ]
    if record.artifacts:
        lines.extend(f"- {name}: `{path}`" for name, path in sorted(record.artifacts.items()))
    else:
        lines.append("- none")

    lines.extend(["", "## Metrics", ""])
    if record.metrics:
        lines.extend(f"- {name}: `{value}`" for name, value in sorted(record.metrics.items()))
    else:
        lines.append("- none")

    lines.extend(["", "## Failure Tags", ""])
    if record.failure_tags:
        lines.extend(f"- `{tag}`" for tag in record.failure_tags)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Next Action",
            "",
            record.next_action or "No next action recorded.",
        ]
    )
    if record.notes:
        lines.extend(["", "## Notes", "", record.notes])
    return "\n".join(lines) + "\n"

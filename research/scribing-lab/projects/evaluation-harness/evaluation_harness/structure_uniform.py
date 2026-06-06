from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from evaluation_harness.artifacts import ArtifactStore
from evaluation_harness.baseline_outline import (
    _json_dumps,
    _series_summary,
    _use_headless_matplotlib,
    strokes_to_trajectory,
)
from evaluation_harness.metrics import compute_text_metrics, compute_trajectory_metrics
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.report import render_markdown_report

DEFAULT_STRUCTURE_INPUTS: tuple[str, ...] = ("永", "あいうえお")
EXTENDED_STRUCTURE_INPUTS: tuple[str, ...] = (
    "永",
    "あいうえお",
    "あああ",
    "いいい",
    "永あい",
    "あおえい",
    "あい\nうえ",
)


@dataclass(frozen=True)
class StructureUniformConfig:
    char_size: float = 8.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_spacing: float = 2.0
    line_height: float = 1.45
    draw_speed_mm_s: float = 40.0
    penup_speed_mm_s: float = 120.0


def run_structure_uniform(
    *,
    root: Path,
    experiment_id: str,
    input_text: str,
    seed: int,
    profile_id: str = "baseline-neat",
    config: StructureUniformConfig | None = None,
) -> ExperimentRecord:
    _ensure_paths()
    _use_headless_matplotlib()

    from character_dictionary import LayoutConfig, layout_text
    from src.gcode.config import PlotterConfig
    from src.gcode.generator import GCodeGenerator
    from src.gcode.preview import preview_strokes

    cfg = config or StructureUniformConfig()
    registry = ExperimentRegistry(root / "registry.jsonl")
    artifacts = ArtifactStore(root / "artifacts")

    laid_out = layout_text(
        input_text,
        LayoutConfig(
            margin_left=cfg.margin_left,
            margin_top=cfg.margin_top,
            char_size=cfg.char_size,
            char_spacing=cfg.char_spacing,
            line_height=cfg.line_height,
        ),
    )
    strokes = [np.array(stroke.points, dtype=float) for stroke in laid_out]
    finishes = [stroke.terminal for stroke in laid_out]
    generator = GCodeGenerator(PlotterConfig())
    gcode_lines = generator.generate(strokes, finishes=finishes, vary_speed=False)
    trajectory = strokes_to_trajectory(
        strokes,
        draw_speed_mm_s=cfg.draw_speed_mm_s,
        penup_speed_mm_s=cfg.penup_speed_mm_s,
    )
    metrics = compute_trajectory_metrics(trajectory)
    metrics.update(
        {
            "structure_stroke_count": len(strokes),
            "gcode_line_count": len(gcode_lines),
            **compute_text_metrics(input_text),
        }
    )

    trajectory_path = artifacts.write_json(experiment_id, "trajectory.json", trajectory)
    template_path = artifacts.write_json(
        experiment_id,
        "stroke_templates.json",
        [
            {
                "literal": stroke.literal,
                "stroke_type": stroke.stroke_type,
                "terminal": stroke.terminal,
                "order": stroke.order,
                "points": [[round(float(x), 4), round(float(y), 4)] for x, y in stroke.points],
            }
            for stroke in laid_out
        ],
    )
    config_path = artifacts.write_json(experiment_id, "structure_config.json", asdict(cfg))
    gcode_path = artifacts.write_text(experiment_id, "output.gcode", "\n".join(gcode_lines) + "\n")
    preview_path = artifacts.experiment_dir(experiment_id) / "preview.png"
    preview_strokes(strokes, save_path=preview_path)

    record = ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="structure-uniform preserves stroke order and terminal events for comparison",
        input_text=input_text,
        profile_id=profile_id,
        seed=seed,
        generator="structure-uniform",
        exporter="xdraw-gcode",
        artifacts={
            "trajectory": trajectory_path,
            "stroke_templates": template_path,
            "structure_config": config_path,
            "gcode": gcode_path,
            "preview": str(preview_path),
        },
        metrics=metrics,
        failure_tags=infer_structure_uniform_failure_tags(input_text),
        next_action="compare against baseline-outline and then add motion timing",
        notes="Structure-uniform uses the character dictionary skeletons with deterministic timing.",
    )
    report_path = artifacts.write_text(experiment_id, "report.md", render_markdown_report(record))
    record = replace(record, artifacts={**record.artifacts, "report": report_path})
    registry.append(record)
    return record


def run_structure_uniform_batch(
    *,
    root: Path,
    input_texts: tuple[str, ...] | list[str] = DEFAULT_STRUCTURE_INPUTS,
    seeds: tuple[int, ...] | list[int] = (1, 2, 3),
    profile_id: str = "baseline-neat",
    config: StructureUniformConfig | None = None,
) -> list[ExperimentRecord]:
    records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(input_texts, start=1):
        for seed in seeds:
            records.append(
                run_structure_uniform(
                    root=root,
                    experiment_id=f"exp-structure-i{input_index:02d}-s{seed:03d}",
                    input_text=input_text,
                    seed=seed,
                    profile_id=profile_id,
                    config=config,
                )
            )

    summary = summarize_structure_records(records)
    root.mkdir(parents=True, exist_ok=True)
    (root / "structure_summary.json").write_text(_json_dumps(summary), encoding="utf-8")
    (root / "structure_summary.md").write_text(render_structure_summary_markdown(summary), encoding="utf-8")
    return records


def infer_structure_uniform_failure_tags(input_text: str) -> list[str]:
    tags = ["too-uniform", "skeleton-too-rigid"]
    if len(input_text) >= 5:
        tags.append("line-too-mechanical")
    return tags


def summarize_structure_records(records: list[ExperimentRecord]) -> dict[str, Any]:
    stroke_counts = [float(record.metrics.get("structure_stroke_count", 0)) for record in records]
    durations = [float(record.metrics.get("duration_ms", 0)) for record in records]
    failure_tag_counts: dict[str, int] = {}
    for record in records:
        for tag in record.failure_tags:
            failure_tag_counts[tag] = failure_tag_counts.get(tag, 0) + 1
    return {
        "record_count": len(records),
        "input_count": len({record.input_text for record in records}),
        "seed_count": len({record.seed for record in records}),
        "failure_tag_counts": failure_tag_counts,
        "structure_stroke_count": _series_summary(stroke_counts),
        "duration_ms": _series_summary(durations),
        "records": [
            {
                "experiment_id": record.experiment_id,
                "input_text": record.input_text,
                "seed": record.seed,
                "structure_stroke_count": record.metrics.get("structure_stroke_count", 0),
                "duration_ms": record.metrics.get("duration_ms", 0),
                "failure_tags": list(record.failure_tags),
            }
            for record in records
        ],
    }


def render_structure_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Structure Uniform Summary",
        "",
        f"- record_count: `{summary['record_count']}`",
        f"- input_count: `{summary['input_count']}`",
        f"- seed_count: `{summary['seed_count']}`",
        f"- failure_tag_counts: `{summary['failure_tag_counts']}`",
        f"- structure_stroke_count: `{summary['structure_stroke_count']}`",
        f"- duration_ms: `{summary['duration_ms']}`",
        "",
        "## Records",
        "",
    ]
    for record in summary["records"]:
        lines.append(
            "- "
            f"{record['experiment_id']}: "
            f"input=`{record['input_text']}`, "
            f"seed=`{record['seed']}`, "
            f"strokes=`{record['structure_stroke_count']}`, "
            f"failure_tags=`{record['failure_tags']}`"
        )
    return "\n".join(lines) + "\n"


def _ensure_paths() -> None:
    current = Path(__file__).resolve()
    repo_root: Path | None = None
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "research").is_dir():
            repo_root = parent
            break
    if repo_root is None:
        raise RuntimeError("Cannot locate pen_plotter repository root")

    paths = [
        repo_root,
        repo_root / "research" / "scribing-lab" / "projects" / "character-dictionary",
    ]
    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from evaluation_harness.artifacts import ArtifactStore
from evaluation_harness.baseline_outline import _json_dumps, _series_summary, _use_headless_matplotlib
from evaluation_harness.metrics import compute_text_metrics, compute_trajectory_metrics
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.report import render_markdown_report
from evaluation_harness.structure_uniform import DEFAULT_STRUCTURE_INPUTS


@dataclass(frozen=True)
class StructureMotionConfig:
    char_size: float = 8.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    char_spacing: float = 2.0
    line_height: float = 1.45
    samples_per_segment: int = 6
    timing_jitter_cv: float = 0.08
    tremor_mm: float = 0.015


def run_structure_motion(
    *,
    root: Path,
    experiment_id: str,
    input_text: str,
    seed: int,
    profile_id: str = "baseline-neat",
    config: StructureMotionConfig | None = None,
) -> ExperimentRecord:
    _ensure_paths()
    _use_headless_matplotlib()

    from character_dictionary import LayoutConfig, layout_text
    from motion_synthesis import MotionConfig, SkeletonStroke, synthesize_motion
    from src.gcode.config import PlotterConfig
    from src.gcode.generator import GCodeGenerator
    from src.gcode.preview import preview_strokes

    cfg = config or StructureMotionConfig()
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
    skeletons = [
        SkeletonStroke(
            points=stroke.points,
            terminal=stroke.terminal,
            literal=stroke.literal,
            stroke_type=stroke.stroke_type,
        )
        for stroke in laid_out
    ]
    strokes = [np.array(stroke.points, dtype=float) for stroke in laid_out]
    finishes = [stroke.terminal for stroke in laid_out]
    trajectory = [
        point.to_dict()
        for point in synthesize_motion(
            skeletons,
            seed=seed,
            config=MotionConfig(
                samples_per_segment=cfg.samples_per_segment,
                timing_jitter_cv=cfg.timing_jitter_cv,
                tremor_mm=cfg.tremor_mm,
            ),
        )
    ]

    generator = GCodeGenerator(PlotterConfig())
    gcode_lines = generator.generate(strokes, finishes=finishes, vary_speed=True)
    metrics = compute_trajectory_metrics(trajectory)
    metrics.update(
        {
            "structure_stroke_count": len(strokes),
            "gcode_line_count": len(gcode_lines),
            **compute_text_metrics(input_text),
        }
    )

    trajectory_path = artifacts.write_json(experiment_id, "trajectory.json", trajectory)
    config_path = artifacts.write_json(experiment_id, "motion_config.json", asdict(cfg))
    gcode_path = artifacts.write_text(experiment_id, "output.gcode", "\n".join(gcode_lines) + "\n")
    preview_path = artifacts.experiment_dir(experiment_id) / "preview.png"
    preview_strokes(strokes, save_path=preview_path)

    record = ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="structure-motion adds non-uniform timing and pressure events to skeleton strokes",
        input_text=input_text,
        profile_id=profile_id,
        seed=seed,
        generator="structure-motion",
        exporter="xdraw-gcode",
        artifacts={
            "trajectory": trajectory_path,
            "motion_config": config_path,
            "gcode": gcode_path,
            "preview": str(preview_path),
        },
        metrics=metrics,
        failure_tags=infer_structure_motion_failure_tags(input_text),
        next_action="compare against structure-uniform and tune skeleton rigidity",
        notes="Structure-motion uses dictionary skeletons with seeded motion timing.",
    )
    report_path = artifacts.write_text(experiment_id, "report.md", render_markdown_report(record))
    record = replace(record, artifacts={**record.artifacts, "report": report_path})
    registry.append(record)
    return record


def run_structure_motion_batch(
    *,
    root: Path,
    input_texts: tuple[str, ...] | list[str] = DEFAULT_STRUCTURE_INPUTS,
    seeds: tuple[int, ...] | list[int] = (1, 2, 3),
    profile_id: str = "baseline-neat",
    config: StructureMotionConfig | None = None,
) -> list[ExperimentRecord]:
    records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(input_texts, start=1):
        for seed in seeds:
            records.append(
                run_structure_motion(
                    root=root,
                    experiment_id=f"exp-motion-i{input_index:02d}-s{seed:03d}",
                    input_text=input_text,
                    seed=seed,
                    profile_id=profile_id,
                    config=config,
                )
            )

    summary = summarize_motion_records(records)
    root.mkdir(parents=True, exist_ok=True)
    (root / "motion_summary.json").write_text(_json_dumps(summary), encoding="utf-8")
    (root / "motion_summary.md").write_text(render_motion_summary_markdown(summary), encoding="utf-8")
    return records


def infer_structure_motion_failure_tags(input_text: str) -> list[str]:
    tags = ["skeleton-too-rigid"]
    if len(input_text) >= 5:
        tags.append("line-too-mechanical")
    return tags


def summarize_motion_records(records: list[ExperimentRecord]) -> dict[str, Any]:
    velocity_peaks = [float(record.metrics.get("velocity_peak_count", 0)) for record in records]
    speed_cv = [float(record.metrics.get("draw_speed_cv", 0.0)) for record in records]
    failure_tag_counts: dict[str, int] = {}
    for record in records:
        for tag in record.failure_tags:
            failure_tag_counts[tag] = failure_tag_counts.get(tag, 0) + 1
    return {
        "record_count": len(records),
        "input_count": len({record.input_text for record in records}),
        "seed_count": len({record.seed for record in records}),
        "failure_tag_counts": failure_tag_counts,
        "velocity_peak_count": _series_summary(velocity_peaks),
        "draw_speed_cv": _series_summary(speed_cv),
        "records": [
            {
                "experiment_id": record.experiment_id,
                "input_text": record.input_text,
                "seed": record.seed,
                "velocity_peak_count": record.metrics.get("velocity_peak_count", 0),
                "draw_speed_cv": record.metrics.get("draw_speed_cv", 0.0),
                "failure_tags": list(record.failure_tags),
            }
            for record in records
        ],
    }


def render_motion_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Structure Motion Summary",
        "",
        f"- record_count: `{summary['record_count']}`",
        f"- input_count: `{summary['input_count']}`",
        f"- seed_count: `{summary['seed_count']}`",
        f"- failure_tag_counts: `{summary['failure_tag_counts']}`",
        f"- velocity_peak_count: `{summary['velocity_peak_count']}`",
        f"- draw_speed_cv: `{summary['draw_speed_cv']}`",
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
            f"velocity_peaks=`{record['velocity_peak_count']}`, "
            f"draw_speed_cv=`{record['draw_speed_cv']}`, "
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
        repo_root / "research" / "scribing-lab" / "projects" / "motion-synthesis",
    ]
    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

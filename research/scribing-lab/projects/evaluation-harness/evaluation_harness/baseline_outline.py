from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from evaluation_harness.artifacts import ArtifactStore
from evaluation_harness.metrics import compute_trajectory_metrics
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.report import render_markdown_report

DEFAULT_EVALUATION_INPUTS: tuple[str, ...] = (
    "永",
    "あいうえお",
    "今日はよい天気です。",
    "春の川をゆっくり歩く。",
    "本日はありがとうございました。",
)


@dataclass(frozen=True)
class BaselineOutlineConfig:
    font_size: float = 7.0
    margin_left: float = 12.0
    margin_top: float = 16.0
    line_height: float = 1.45
    char_spacing: float = 0.8
    jitter: float = 0.08
    wobble: float = 0.04
    optimize: bool = True
    vary_speed: bool = True
    draw_speed_mm_s: float = 40.0
    penup_speed_mm_s: float = 120.0


def run_baseline_outline(
    *,
    root: Path,
    experiment_id: str,
    input_text: str,
    seed: int,
    profile_id: str = "baseline-neat",
    config: BaselineOutlineConfig | None = None,
) -> ExperimentRecord:
    """Run the fixed font-outline baseline and register its artifacts."""
    _ensure_repo_root_on_path()

    from src.gcode.config import PlotterConfig
    from src.gcode.generator import GCodeGenerator
    from src.gcode.optimizer import optimize_stroke_order
    from src.gcode.preview import preview_strokes
    from src.textplot import RenderConfig, render_text

    cfg = config or BaselineOutlineConfig()
    registry = ExperimentRegistry(root / "registry.jsonl")
    artifacts = ArtifactStore(root / "artifacts")

    render_config = RenderConfig(
        font_size=cfg.font_size,
        margin_left=cfg.margin_left,
        margin_top=cfg.margin_top,
        line_height=cfg.line_height,
        char_spacing=cfg.char_spacing,
        jitter=cfg.jitter,
        wobble=cfg.wobble,
        seed=seed,
    )
    strokes = render_text(input_text, render_config)
    if cfg.optimize:
        strokes = optimize_stroke_order(strokes, start_pos=(0.0, render_config.paper_height))

    generator = GCodeGenerator(PlotterConfig())
    gcode_lines = generator.generate(strokes, vary_speed=cfg.vary_speed)
    trajectory = strokes_to_trajectory(
        strokes,
        draw_speed_mm_s=cfg.draw_speed_mm_s,
        penup_speed_mm_s=cfg.penup_speed_mm_s,
    )
    metrics = compute_trajectory_metrics(trajectory)
    metrics.update(
        {
            "baseline_stroke_count": len(strokes),
            "gcode_line_count": len(gcode_lines),
        }
    )

    trajectory_path = artifacts.write_json(experiment_id, "trajectory.json", trajectory)
    strokes_path = artifacts.write_json(experiment_id, "strokes.json", _strokes_to_json(strokes))
    config_path = artifacts.write_json(
        experiment_id,
        "render_config.json",
        {
            "baseline": asdict(cfg),
            "render": _render_config_to_dict(render_config),
        },
    )
    gcode_path = artifacts.write_text(experiment_id, "output.gcode", "\n".join(gcode_lines) + "\n")
    preview_path = artifacts.experiment_dir(experiment_id) / "preview.png"
    preview_strokes(strokes, save_path=preview_path)

    record = ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="baseline-outline fixes the current font outline generator for comparison",
        input_text=input_text,
        profile_id=profile_id,
        seed=seed,
        generator="baseline-outline",
        exporter="xdraw-gcode",
        artifacts={
            "trajectory": trajectory_path,
            "strokes": strokes_path,
            "render_config": config_path,
            "gcode": gcode_path,
            "preview": str(preview_path),
        },
        metrics=metrics,
        failure_tags=[],
        next_action="compare this baseline against structure and motion generators with the same seed",
        notes=(
            "Trajectory timing is approximated from outline stroke geometry because the current "
            "baseline generator does not emit online handwriting timestamps."
        ),
    )
    report_path = artifacts.write_text(experiment_id, "report.md", render_markdown_report(record))
    record = replace(record, artifacts={**record.artifacts, "report": report_path})
    registry.append(record)
    return record


def run_baseline_outline_batch(
    *,
    root: Path,
    input_texts: list[str] | tuple[str, ...] = DEFAULT_EVALUATION_INPUTS,
    seeds: list[int] | tuple[int, ...] = (1, 2, 3),
    profile_id: str = "baseline-neat",
    config: BaselineOutlineConfig | None = None,
) -> list[ExperimentRecord]:
    records: list[ExperimentRecord] = []
    for input_index, input_text in enumerate(input_texts, start=1):
        for seed in seeds:
            experiment_id = f"exp-baseline-i{input_index:02d}-s{seed:03d}"
            records.append(
                run_baseline_outline(
                    root=root,
                    experiment_id=experiment_id,
                    input_text=input_text,
                    seed=seed,
                    profile_id=profile_id,
                    config=config,
                )
            )

    summary = summarize_records(records)
    root.mkdir(parents=True, exist_ok=True)
    summary_json = root / "summary.json"
    summary_md = root / "summary.md"
    summary_json.write_text(_json_dumps(summary), encoding="utf-8")
    summary_md.write_text(render_summary_markdown(summary), encoding="utf-8")
    return records


def summarize_records(records: list[ExperimentRecord]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    stroke_counts: list[float] = []
    draw_distances: list[float] = []
    penup_distances: list[float] = []
    durations: list[float] = []

    for record in records:
        status = str(record.metrics.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        stroke_counts.append(float(record.metrics.get("baseline_stroke_count", 0)))
        draw_distances.append(float(record.metrics.get("draw_distance_mm", 0.0)))
        penup_distances.append(float(record.metrics.get("penup_distance_mm", 0.0)))
        durations.append(float(record.metrics.get("duration_ms", 0)))

    return {
        "record_count": len(records),
        "input_count": len({record.input_text for record in records}),
        "seed_count": len({record.seed for record in records}),
        "status_counts": status_counts,
        "baseline_stroke_count": _series_summary(stroke_counts),
        "draw_distance_mm": _series_summary(draw_distances),
        "penup_distance_mm": _series_summary(penup_distances),
        "duration_ms": _series_summary(durations),
        "records": [
            {
                "experiment_id": record.experiment_id,
                "input_text": record.input_text,
                "seed": record.seed,
                "status": record.metrics.get("status", "unknown"),
                "baseline_stroke_count": record.metrics.get("baseline_stroke_count", 0),
                "draw_distance_mm": record.metrics.get("draw_distance_mm", 0.0),
                "penup_distance_mm": record.metrics.get("penup_distance_mm", 0.0),
                "duration_ms": record.metrics.get("duration_ms", 0),
                "report": record.artifacts.get("report", ""),
            }
            for record in records
        ],
    }


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Baseline Outline Summary",
        "",
        f"- record_count: `{summary['record_count']}`",
        f"- input_count: `{summary['input_count']}`",
        f"- seed_count: `{summary['seed_count']}`",
        f"- status_counts: `{summary['status_counts']}`",
        "",
        "## Metric Summary",
        "",
    ]
    for key in ("baseline_stroke_count", "draw_distance_mm", "penup_distance_mm", "duration_ms"):
        lines.append(f"- {key}: `{summary[key]}`")

    lines.extend(["", "## Records", ""])
    for record in summary["records"]:
        lines.append(
            "- "
            f"{record['experiment_id']}: "
            f"input=`{record['input_text']}`, "
            f"seed=`{record['seed']}`, "
            f"strokes=`{record['baseline_stroke_count']}`, "
            f"duration_ms=`{record['duration_ms']}`"
        )
    return "\n".join(lines) + "\n"


def strokes_to_trajectory(
    strokes: list[np.ndarray],
    *,
    draw_speed_mm_s: float,
    penup_speed_mm_s: float,
) -> list[dict[str, float | int]]:
    """Convert outline strokes into a deterministic approximate online trajectory."""
    t_ms = 0.0
    current = np.array([0.0, 297.0], dtype=float)
    points: list[dict[str, float | int]] = [
        {"x": float(current[0]), "y": float(current[1]), "t": 0, "pen_state": 0, "pressure": 0.0}
    ]

    for stroke in strokes:
        if len(stroke) < 2:
            continue

        start = stroke[0]
        t_ms += _duration_ms(current, start, penup_speed_mm_s)
        points.append(
            {
                "x": round(float(start[0]), 4),
                "y": round(float(start[1]), 4),
                "t": int(round(t_ms)),
                "pen_state": 0,
                "pressure": 0.0,
            }
        )
        points.append(
            {
                "x": round(float(start[0]), 4),
                "y": round(float(start[1]), 4),
                "t": int(round(t_ms)),
                "pen_state": 1,
                "pressure": 1.0,
            }
        )

        prev = start
        for point in stroke[1:]:
            t_ms += _duration_ms(prev, point, draw_speed_mm_s)
            points.append(
                {
                    "x": round(float(point[0]), 4),
                    "y": round(float(point[1]), 4),
                    "t": int(round(t_ms)),
                    "pen_state": 1,
                    "pressure": 1.0,
                }
            )
            prev = point

        points.append(
            {
                "x": round(float(prev[0]), 4),
                "y": round(float(prev[1]), 4),
                "t": int(round(t_ms)),
                "pen_state": 0,
                "pressure": 0.0,
            }
        )
        current = prev

    return points


def _duration_ms(a: np.ndarray, b: np.ndarray, speed_mm_s: float) -> float:
    if speed_mm_s <= 0:
        raise ValueError("speed_mm_s must be positive")
    return float(np.linalg.norm(b - a) / speed_mm_s * 1000.0)


def _strokes_to_json(strokes: list[np.ndarray]) -> list[list[list[float]]]:
    return [
        [[round(float(x), 4), round(float(y), 4)] for x, y in stroke.tolist()] for stroke in strokes
    ]


def _render_config_to_dict(config: Any) -> dict[str, Any]:
    data = asdict(config)
    data["font_path"] = str(data["font_path"]) if data["font_path"] is not None else None
    return data


def _series_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(sum(values) / len(values), 4),
    }


def _json_dumps(data: Any) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _ensure_repo_root_on_path() -> None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "pyproject.toml").is_file():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return
    raise RuntimeError("Cannot locate pen_plotter repository root")

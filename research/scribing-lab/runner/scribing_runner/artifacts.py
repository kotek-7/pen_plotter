from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from scribing_runner.contracts import RunArtifacts, RunRequest


def default_lab_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_engine_path() -> Path:
    return default_lab_root() / "engines" / "basic_stroke_engine"


def default_run_dir(engine_id: str, *, run_name: str | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    label = _safe_run_label(run_name or engine_id)
    runs_dir = default_lab_root() / "runs"
    candidate = runs_dir / f"{stamp}_{label}"
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        suffixed = runs_dir / f"{stamp}_{label}-{index:02d}"
        if not suffixed.exists():
            return suffixed
    raise RuntimeError(f"failed to allocate run directory for {stamp}_{label}")


def write_run_artifacts(
    *,
    run_dir: Path,
    request: RunRequest,
    result: dict[str, Any],
) -> RunArtifacts:
    run_dir.mkdir(parents=True, exist_ok=True)

    engine_id = str(result.get("engine_id", "unknown-engine"))
    trajectory = result.get("trajectory", [])
    engine_parameters = result.get("engine_parameters", {})

    # runner only persists the canonical trajectory and run metadata. preview /
    # gcode / safety are produced separately by the renderer / exporter bases,
    # which read this trajectory.json. runner stays decoupled from them.
    input_path = run_dir / "input.txt"
    memo_path = run_dir / "memo.md"
    trajectory_path = run_dir / "trajectory.json"

    input_path.write_text(request.text, encoding="utf-8")
    memo_path.write_text(
        render_memo(
            engine_id=engine_id,
            request=request,
            engine_parameters=engine_parameters,
        ),
        encoding="utf-8",
    )
    trajectory_path.write_text(_json_dumps(trajectory), encoding="utf-8")

    return RunArtifacts(
        run_dir=run_dir,
        memo=memo_path,
        input_text=input_path,
        trajectory=trajectory_path,
    )


def render_memo(
    *,
    engine_id: str,
    request: RunRequest,
    engine_parameters: Any,
) -> str:
    lines = [
        "# Run Memo",
        "",
        f"engine: {engine_id}",
        f"seed: {request.seed}",
        "input: input.txt",
        "",
        "## Parameters",
        "",
    ]
    if request.params:
        for key, value in sorted(request.params.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- default")

    lines.extend(
        [
            "",
            "## Engine Parameters Snapshot",
            "",
            "```json",
            json.dumps(engine_parameters, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _safe_run_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    label = label.strip(".-_")
    return label or "run"

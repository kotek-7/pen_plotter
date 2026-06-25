from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunRequest:
    text: str
    seed: int
    params: dict[str, str] = field(default_factory=dict)
    engine_path: Path | None = None

    def to_engine_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "seed": self.seed,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    memo: Path
    input_text: Path
    trajectory: Path
    preview: Path
    gcode: Path
    safety: Path


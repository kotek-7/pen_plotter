from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    hypothesis: str
    input_text: str
    profile_id: str
    seed: int
    generator: str
    exporter: str
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    failure_tags: list[str] = field(default_factory=list)
    next_action: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis": self.hypothesis,
            "input_text": self.input_text,
            "profile_id": self.profile_id,
            "seed": self.seed,
            "generator": self.generator,
            "exporter": self.exporter,
            "artifacts": dict(self.artifacts),
            "metrics": dict(self.metrics),
            "failure_tags": list(self.failure_tags),
            "next_action": self.next_action,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentRecord:
        return cls(
            experiment_id=str(data["experiment_id"]),
            hypothesis=str(data["hypothesis"]),
            input_text=str(data["input_text"]),
            profile_id=str(data["profile_id"]),
            seed=int(data["seed"]),
            generator=str(data["generator"]),
            exporter=str(data["exporter"]),
            artifacts={str(k): str(v) for k, v in data.get("artifacts", {}).items()},
            metrics=dict(data.get("metrics", {})),
            failure_tags=[str(tag) for tag in data.get("failure_tags", [])],
            next_action=str(data.get("next_action", "")),
            notes=str(data.get("notes", "")),
        )

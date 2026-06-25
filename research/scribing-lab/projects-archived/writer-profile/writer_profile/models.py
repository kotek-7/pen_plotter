from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WriterProfileParameters:
    slant_deg: float = 0.0
    spacing_mean_mm: float = 1.2
    speed_mean_mm_s: float = 40.0
    harai_gain: float = 1.0
    hane_gain: float = 1.0
    tome_gain: float = 1.0
    timing_jitter_cv: float = 0.08
    tremor_mm: float = 0.015
    baseline_drift_mm: float = 0.0
    shape_variation: float = 0.0
    layout_variation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WriterProfile:
    profile_id: str
    version: int
    source: str
    allowed_use: str
    params: WriterProfileParameters
    parent_profile: str | None = None
    created_from_experiment: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "source": self.source,
            "allowed_use": self.allowed_use,
            "params": self.params.to_dict(),
            "parent_profile": self.parent_profile,
            "created_from_experiment": self.created_from_experiment,
            "notes": self.notes,
        }

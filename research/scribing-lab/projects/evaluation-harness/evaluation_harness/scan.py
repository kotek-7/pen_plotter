from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScanMetadata:
    scanner: str
    resolution_dpi: int
    crop_method: str
    pen_type: str
    paper_type: str
    plotter: str
    captured_at: str
    operator_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanMetadata:
        return cls(
            scanner=str(data["scanner"]),
            resolution_dpi=int(data["resolution_dpi"]),
            crop_method=str(data["crop_method"]),
            pen_type=str(data["pen_type"]),
            paper_type=str(data["paper_type"]),
            plotter=str(data["plotter"]),
            captured_at=str(data["captured_at"]),
            operator_note=str(data.get("operator_note", "")),
        )


def validate_scan_metadata(metadata: ScanMetadata) -> None:
    required = {
        "scanner": metadata.scanner,
        "crop_method": metadata.crop_method,
        "pen_type": metadata.pen_type,
        "paper_type": metadata.paper_type,
        "plotter": metadata.plotter,
        "captured_at": metadata.captured_at,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise ValueError(f"Missing scan metadata fields: {', '.join(missing)}")
    if metadata.resolution_dpi <= 0:
        raise ValueError("resolution_dpi must be positive")

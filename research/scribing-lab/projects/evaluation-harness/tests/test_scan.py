import pytest

from evaluation_harness.artifacts import ArtifactStore
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.scan import ScanMetadata, attach_scan_artifact, validate_scan_metadata


def test_scan_metadata_round_trips_dict() -> None:
    metadata = ScanMetadata(
        scanner="flatbed-a",
        resolution_dpi=600,
        crop_method="manual-a4-corners",
        pen_type="mechanical-pencil-hb",
        paper_type="plain-a4",
        plotter="xdraw-a4",
        captured_at="2026-06-05T12:00:00+09:00",
        operator_note="baseline scan",
    )

    restored = ScanMetadata.from_dict(metadata.to_dict())

    assert restored == metadata


def test_validate_scan_metadata_rejects_missing_required_field() -> None:
    metadata = ScanMetadata(
        scanner="",
        resolution_dpi=600,
        crop_method="manual",
        pen_type="mechanical-pencil-hb",
        paper_type="plain-a4",
        plotter="xdraw-a4",
        captured_at="2026-06-05T12:00:00+09:00",
    )

    with pytest.raises(ValueError, match="scanner"):
        validate_scan_metadata(metadata)


def test_validate_scan_metadata_rejects_invalid_resolution() -> None:
    metadata = ScanMetadata(
        scanner="flatbed-a",
        resolution_dpi=0,
        crop_method="manual",
        pen_type="mechanical-pencil-hb",
        paper_type="plain-a4",
        plotter="xdraw-a4",
        captured_at="2026-06-05T12:00:00+09:00",
    )

    with pytest.raises(ValueError, match="resolution_dpi"):
        validate_scan_metadata(metadata)


def test_attach_scan_artifact_updates_registry(tmp_path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    artifacts = ArtifactStore(tmp_path / "artifacts")
    registry.append(
        ExperimentRecord(
            experiment_id="exp-000001",
            hypothesis="test",
            input_text="永",
            profile_id="baseline-neat",
            seed=1,
            generator="baseline-outline",
            exporter="xdraw-gcode",
        )
    )
    scan_path = tmp_path / "scan.png"
    scan_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    metadata = ScanMetadata(
        scanner="flatbed-a",
        resolution_dpi=600,
        crop_method="manual",
        pen_type="mechanical-pencil-hb",
        paper_type="plain-a4",
        plotter="xdraw-a4",
        captured_at="2026-06-05T12:00:00+09:00",
    )

    attach_scan_artifact(
        registry=registry,
        artifacts=artifacts,
        experiment_id="exp-000001",
        scan_path=scan_path,
        metadata=metadata,
    )

    record = registry.get("exp-000001")
    assert "plotted_scan" in record.artifacts
    assert "scan_metadata" in record.artifacts
    assert (tmp_path / "artifacts" / "exp-000001" / "plotted_scan.png").exists()

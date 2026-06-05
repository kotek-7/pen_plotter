import pytest

from evaluation_harness.scan import ScanMetadata, validate_scan_metadata


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

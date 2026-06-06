from pathlib import Path

from writer_profile import (
    estimate_writer_profile_from_jsonl,
    load_handwriting_points_jsonl,
    summarize_handwriting_samples,
)


def test_load_handwriting_points_jsonl_groups_data(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    path.write_text(
        "\n".join(
            [
                _point_line("sample-1", "writer-a", "永", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 1.0, 1.0, 10, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 2.0, 2.0, 20, 1, 1.2),
                _point_line("sample-1", "writer-a", "永", 2.5, 2.2, 30, 0, None),
                _point_line("sample-1", "writer-a", "永", 3.0, 2.4, 50, 1, 0.8),
                _point_line("sample-1", "writer-a", "永", 4.0, 2.6, 60, 1, 0.7),
                _point_line("sample-2", "writer-b", "あ", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 0.5, 1.0, 20, 1, 1.1),
                _point_line("sample-2", "writer-b", "あ", 1.5, 2.5, 40, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 2.0, 3.0, 50, 0, None),
                _point_line("sample-2", "writer-b", "あ", 3.0, 3.2, 80, 1, 0.9),
                _point_line("sample-2", "writer-b", "あ", 4.0, 3.4, 100, 1, 0.85),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_handwriting_points_jsonl(path)
    summary = summarize_handwriting_samples(records)

    assert len(records) == 12
    assert summary["sample_count"] == 2
    assert summary["writer_count"] == 2
    assert summary["text_count"] == 2
    assert summary["stroke_count"] == 4
    assert summary["source_counts"] == {"stylus": 2}
    assert summary["license_scope_counts"] == {"research-only": 2}
    assert summary["mean_speed_mm_s"] > 0
    assert summary["spacing_mean_mm"] > 0
    assert summary["slant_deg"] != 0


def test_estimate_writer_profile_from_jsonl_builds_derived_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "samples.jsonl"
    path.write_text(
        "\n".join(
            [
                _point_line("sample-1", "writer-a", "永", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 1.0, 1.0, 10, 1, 1.0),
                _point_line("sample-1", "writer-a", "永", 2.0, 2.0, 20, 1, 1.2),
                _point_line("sample-1", "writer-a", "永", 2.5, 2.2, 30, 0, None),
                _point_line("sample-1", "writer-a", "永", 3.0, 2.4, 50, 1, 0.8),
                _point_line("sample-1", "writer-a", "永", 4.0, 2.6, 60, 1, 0.7),
                _point_line("sample-2", "writer-b", "あ", 0.0, 0.0, 0, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 0.5, 1.0, 20, 1, 1.1),
                _point_line("sample-2", "writer-b", "あ", 1.5, 2.5, 40, 1, 1.0),
                _point_line("sample-2", "writer-b", "あ", 2.0, 3.0, 50, 0, None),
                _point_line("sample-2", "writer-b", "あ", 3.0, 3.2, 80, 1, 0.9),
                _point_line("sample-2", "writer-b", "あ", 4.0, 3.4, 100, 1, 0.85),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    estimate = estimate_writer_profile_from_jsonl(path)
    profile = estimate["profile"]
    summary = estimate["summary"]

    assert estimate["base_profile_id"] == "baseline-neat"
    assert profile.profile_id.startswith("baseline-neat-data-prior-")
    assert profile.source == "data-driven"
    assert profile.parent_profile == "baseline-neat"
    assert profile.created_from_experiment == "handwriting-prior:2"
    assert profile.params.speed_mean_mm_s != 40.0
    assert profile.params.spacing_mean_mm != 1.2
    assert profile.params.baseline_drift_mm >= 0.0
    assert summary["sample_count"] == 2
    assert summary["stroke_count"] == 4
    assert "data-driven prior from 2 samples / 2 writers" in profile.notes


def _point_line(
    sample_id: str,
    writer_id: str,
    char_or_text: str,
    x_mm: float,
    y_mm: float,
    t_ms: int,
    pen_state: int,
    pressure_optional: float | None,
) -> str:
    return (
        "{"
        f"\"sample_id\": \"{sample_id}\", "
        f"\"writer_id\": \"{writer_id}\", "
        f"\"char_or_text\": \"{char_or_text}\", "
        f"\"x_mm\": {x_mm}, "
        f"\"y_mm\": {y_mm}, "
        f"\"t_ms\": {t_ms}, "
        f"\"pen_state\": {pen_state}, "
        f"\"pressure_optional\": {json_value(pressure_optional)}, "
        "\"source\": \"stylus\", "
        "\"license_scope\": \"research-only\""
        "}"
    )


def json_value(value: float | None) -> str:
    if value is None:
        return "null"
    return str(value)

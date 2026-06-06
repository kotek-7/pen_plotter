from __future__ import annotations

import json
from pathlib import Path

from writer_profile import (
    convert_finnbusse_handwriting_v1_entry,
    convert_finnbusse_handwriting_v1_jsonl,
)


def test_convert_finnbusse_handwriting_v1_entry_builds_canonical_points() -> None:
    entry = {
        "id": "sample-1",
        "text": "永",
        "scale": 0.5,
        "session_id": "session-a",
        "points": [
            {"dx": 1.0, "dy": 0.0, "eos": 0},
            {"dx": 0.0, "dy": 0.5, "eos": 1},
            {"dx": -0.5, "dy": 0.0, "eos": 0},
        ],
    }

    points = convert_finnbusse_handwriting_v1_entry(entry)

    assert len(points) == 4
    assert [point.pen_state for point in points] == [1, 1, 0, 1]
    assert [point.writer_id for point in points] == ["session:session-a"] * 4
    assert points[0].x_mm == 2.0
    assert points[1].y_mm == 1.0
    assert points[2].pen_state == 0
    assert points[2].x_mm == points[1].x_mm
    assert points[2].y_mm == points[1].y_mm
    assert points[2].t_ms > points[1].t_ms
    assert points[3].t_ms >= points[2].t_ms


def test_convert_finnbusse_handwriting_v1_jsonl_writes_canonical_points(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    out_path = tmp_path / "canonical.jsonl"
    raw_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "sample-1",
                        "text": "Kamera",
                        "scale": 0.25,
                        "session_id": "session-z",
                        "points": [
                            {"dx": 0.5, "dy": 0.0, "eos": 0},
                            {"dx": 0.5, "dy": 0.25, "eos": 1},
                        ],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stats = convert_finnbusse_handwriting_v1_jsonl(raw_path, out_path)

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert stats["raw_sample_count"] == 1
    assert stats["sample_count"] == 1
    assert stats["writer_count"] == 1
    assert stats["canonical_point_count"] == len(lines)
    assert stats["writer_ids"] == ["session:session-z"]

    records = [json.loads(line) for line in lines]
    assert len(records) == 3
    assert records[0]["sample_id"] == "sample-1"
    assert records[0]["char_or_text"] == "Kamera"
    assert records[0]["source"] == "finnbusse/handwriting-v1"
    assert records[0]["license_scope"] == "MIT"
    assert records[1]["pen_state"] == 1
    assert records[2]["pen_state"] == 0

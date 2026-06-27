from __future__ import annotations

import json
from pathlib import Path

from scribing_dataset_viewer.viewer import _dataset_name_from_path, list_datasets


def _write_sample(char: str) -> str:
    return json.dumps(
        {
            "writerId": "self_001",
            "charsetName": "hiragana_basic",
            "char": char,
            "canvas": {"width": 100, "height": 100},
            "strokes": [{"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}],
        }
    )


def test_list_datasets_reads_meta(tmp_path: Path) -> None:
    raw = tmp_path / "handwriting_raw_self_001_hiragana_basic_20260626_010101.jsonl"
    raw.write_text(_write_sample("あ") + "\n" + _write_sample("い") + "\n", encoding="utf-8")
    meta = tmp_path / "handwriting_meta_self_001_hiragana_basic_20260626_010101.json"
    meta.write_text(json.dumps({"writer_id": "self_001", "charset": "hiragana_basic"}), encoding="utf-8")

    infos = list_datasets(tmp_path)

    assert len(infos) == 1
    assert infos[0].sample_count == 2
    assert infos[0].writer == "self_001"
    assert infos[0].charset == "hiragana_basic"
    assert infos[0].to_dict()["data_url"].endswith(raw.name)


def test_list_datasets_falls_back_to_first_line(tmp_path: Path) -> None:
    raw = tmp_path / "data.jsonl"
    raw.write_text(_write_sample("う") + "\n", encoding="utf-8")

    infos = list_datasets(tmp_path)

    assert infos[0].writer == "self_001"
    assert infos[0].charset == "hiragana_basic"
    assert infos[0].sample_count == 1


def test_dataset_name_from_path() -> None:
    assert _dataset_name_from_path("/dataset/data.jsonl") == "data.jsonl"
    assert _dataset_name_from_path("/dataset/a%20b.jsonl") == "a b.jsonl"
    assert _dataset_name_from_path("/other") is None

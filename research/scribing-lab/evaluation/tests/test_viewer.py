from __future__ import annotations

from pathlib import Path

from scribing_evaluation.viewer import _run_name_from_path, list_run_previews


def test_list_run_previews_returns_runs_with_preview(tmp_path: Path) -> None:
    older = tmp_path / "20260626T120000_old"
    newer = tmp_path / "20260626T130000_new"
    ignored = tmp_path / "20260626T140000_empty"
    older.mkdir()
    newer.mkdir()
    ignored.mkdir()
    older.joinpath("preview.svg").write_text("<svg></svg>", encoding="utf-8")
    newer.joinpath("preview.svg").write_text("<svg></svg>", encoding="utf-8")
    newer.joinpath("memo.md").write_text("memo", encoding="utf-8")

    runs = list_run_previews(tmp_path)

    assert [run.name for run in runs] == ["20260626T130000_new", "20260626T120000_old"]
    assert runs[0].has_memo is True
    assert runs[1].has_memo is False


def test_list_run_previews_can_focus_one_run(tmp_path: Path) -> None:
    run = tmp_path / "custom-run"
    run.mkdir()
    run.joinpath("preview.svg").write_text("<svg></svg>", encoding="utf-8")

    runs = list_run_previews(tmp_path / "missing", run_dir=run)

    assert [item.name for item in runs] == ["custom-run"]


def test_run_name_from_path_handles_preview_and_memo_routes() -> None:
    assert (
        _run_name_from_path("/preview/20260626T120000_smoke/preview.svg", filename="preview.svg")
        == "20260626T120000_smoke"
    )
    assert _run_name_from_path("/memo/20260626T120000_smoke", filename="memo.md") == (
        "20260626T120000_smoke"
    )
    assert _run_name_from_path("/preview/bad", filename="preview.svg") is None

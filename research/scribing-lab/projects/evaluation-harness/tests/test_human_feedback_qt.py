from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel  # noqa: E402

from evaluation_harness.human_feedback_common import HumanFeedbackDraft  # noqa: E402
from evaluation_harness.human_feedback_qt import HumanFeedbackQtWindow  # noqa: E402
from evaluation_harness.models import ExperimentRecord  # noqa: E402
from evaluation_harness.registry import ExperimentRegistry  # noqa: E402


def test_qt_feedback_ui_uses_regular_weight_fonts() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    assert window._body_font.bold() is False
    assert window._body_bold_font.bold() is False
    assert window._heading_font.bold() is False


def test_qt_feedback_ui_uses_separate_review_guide_and_status_summary() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    assert window._guide_button.text() == "Review Guide"
    assert "missing=" in window.statusBar().currentMessage()


def test_qt_feedback_ui_shows_revision_brief_and_exports_it(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": ["spacing-too-wide"],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {
        "exp-a": HumanFeedbackDraft(
            experiment_id="exp-a",
            decision="needs-tuning",
            reason_tags=["spacing-too-wide"],
            notes="字間が広い",
            reviewer_id="reviewer-1",
        )
    }

    window = HumanFeedbackQtWindow(
        packet=packet,
        drafts=drafts,
        responses_json_path=tmp_path / "human_review_responses.json",
        summary_json_path=tmp_path / "human_review_response_summary.json",
        brief_json_path=tmp_path / "human_review_revision_brief.json",
        brief_markdown_path=tmp_path / "human_review_revision_brief.md",
    )

    monkeypatch.setattr("evaluation_harness.human_feedback_qt.QMessageBox.information", lambda *args, **kwargs: None)

    assert window._detail_tabs.count() == 6
    assert "Revision Brief" in window._brief_text.toPlainText()
    assert "Revision Plan" in window._plan_text.toPlainText()
    assert "Preview Run" in window._preview_run_text.toPlainText()

    window._export_revision_brief()

    brief_md = (tmp_path / "human_review_revision_brief.md").read_text(encoding="utf-8")
    brief_json = (tmp_path / "human_review_revision_brief.json").read_text(encoding="utf-8")
    plan_md = (tmp_path / "human_review_revision_plan.md").read_text(encoding="utf-8")
    plan_json = (tmp_path / "human_review_revision_plan.json").read_text(encoding="utf-8")

    assert "Human Review Revision Brief" in brief_md
    assert "字間が広い" in brief_md
    assert '"brief_status": "ready"' in brief_json
    assert "Human Review Revision Plan" in plan_md
    assert '"plan_status": "ready"' in plan_json


def test_qt_feedback_ui_exports_preview_revision_run(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_report = root / "baseline.md"
    candidate_report = root / "candidate.md"
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    baseline_report.write_text("baseline", encoding="utf-8")
    candidate_report.write_text("candidate", encoding="utf-8")
    registry.append(
        ExperimentRecord.from_dict(
            {
                "experiment_id": "exp-baseline",
                "hypothesis": "baseline",
                "input_text": "永",
                "profile_id": "baseline-neat",
                "seed": 1,
                "generator": "baseline-outline",
                "exporter": "preview",
                "artifacts": {"preview": str(baseline_preview), "report": str(baseline_report)},
                "metrics": {"draw_speed_cv": 0.0},
                "failure_tags": [],
                "next_action": "keep baseline comparison",
                "notes": "",
            }
        )
    )
    registry.append(
        ExperimentRecord.from_dict(
            {
                "experiment_id": "exp-candidate",
                "hypothesis": "candidate",
                "input_text": "永",
                "profile_id": "fast-casual",
                "seed": 1,
                "generator": "structure-motion",
                "exporter": "preview",
                "artifacts": {"preview": str(candidate_preview), "report": str(candidate_report)},
                "metrics": {
                    "draw_speed_cv": 0.01,
                    "shape_variation_mm": 0.6,
                    "layout_variation_mm": 0.6,
                },
                "failure_tags": ["spacing-too-wide"],
                "next_action": "adjust spacing",
                "notes": "",
            }
        )
    )

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-candidate",
                "input_text": "永",
                "seed": 1,
                "reason": "test",
                "failure_tags": ["spacing-too-wide"],
                "metrics": {},
                "preview": str(candidate_preview),
            }
        ]
    }
    drafts = {
        "exp-candidate": HumanFeedbackDraft(
            experiment_id="exp-candidate",
            decision="needs-tuning",
            reason_tags=["spacing-too-wide"],
            notes="字間が広い",
            reviewer_id="reviewer-1",
        )
    }

    window = HumanFeedbackQtWindow(
        packet=packet,
        drafts=drafts,
        responses_json_path=root / "human_review_responses.json",
        summary_json_path=root / "human_review_response_summary.json",
        brief_json_path=root / "human_review_revision_brief.json",
        brief_markdown_path=root / "human_review_revision_brief.md",
        plan_json_path=root / "human_review_revision_plan.json",
        plan_markdown_path=root / "human_review_revision_plan.md",
        preview_run_json_path=root / "human_review_preview_revision_run.json",
        preview_run_markdown_path=root / "human_review_preview_revision_run.md",
        base_dir=root,
    )

    monkeypatch.setattr("evaluation_harness.human_feedback_qt.QMessageBox.information", lambda *args, **kwargs: None)

    window._export_preview_revision_run()

    preview_run_md = (root / "human_review_preview_revision_run.md").read_text(encoding="utf-8")
    preview_run_json = (root / "human_review_preview_revision_run.json").read_text(encoding="utf-8")
    brief_md = (root / "human_review_revision_brief.md").read_text(encoding="utf-8")
    plan_md = (root / "human_review_revision_plan.md").read_text(encoding="utf-8")

    assert "Preview Revision Loop" in preview_run_md
    assert "Human Review Preview Revision Plan" in window._preview_run_text.toPlainText()
    assert '"expected_input_texts": [\n      "永"\n    ]' in preview_run_json
    assert '"expected_seeds": [\n      1\n    ]' in preview_run_json
    assert '"rerun_count": 1' in preview_run_json
    assert '"rerun_plan_count": 1' in preview_run_json
    assert "Human Review Revision Brief" in brief_md
    assert "Human Review Revision Plan" in plan_md


def test_qt_feedback_ui_accepts_preview_run_output_paths(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(
        packet=packet,
        drafts=drafts,
        preview_run_json_path=tmp_path / "preview_run.json",
        preview_run_markdown_path=tmp_path / "preview_run.md",
    )

    assert window._preview_run_json_path == tmp_path / "preview_run.json"
    assert window._preview_run_markdown_path == tmp_path / "preview_run.md"


def test_qt_feedback_ui_defaults_to_zoomed_preview() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    assert window._preview_zoom > 1.0
    window._set_preview_zoom(10.0)
    assert window._preview_zoom == 10.0
    window._set_preview_zoom(0.1)
    assert window._preview_zoom == 0.2


def test_qt_feedback_ui_applies_wheel_zoom_as_relative_factor() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    start_zoom = window._preview_zoom
    window._adjust_preview_zoom(1.08)
    window._adjust_preview_zoom(1.08)

    assert window._preview_zoom == pytest.approx(start_zoom * 1.08 * 1.08)


def test_qt_feedback_ui_uses_tabbed_detail_panel() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": [],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    assert window._detail_tabs.count() == 6
    assert window._detail_tabs.minimumWidth() >= 360
    assert window._preview_view.minimumWidth() >= 760
    assert window._preview_view.minimumHeight() >= 820


def test_qt_feedback_ui_shows_reason_tag_legend_and_tooltips() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    packet = {
        "representatives": [
            {
                "experiment_id": "exp-a",
                "input_text": "今日はよい天気です。",
                "seed": 1,
                "reason": "test",
                "failure_tags": ["too-font-like", "terminal-too-uniform"],
                "metrics": {},
                "preview": "",
            }
        ]
    }
    drafts = {"exp-a": HumanFeedbackDraft(experiment_id="exp-a")}

    window = HumanFeedbackQtWindow(packet=packet, drafts=drafts)

    tooltip = None
    for index in range(window._reason_tags_list.count()):
        item = window._reason_tags_list.item(index)
        if item is not None and item.text().startswith("too-font-like"):
            tooltip = item.toolTip()
            assert "[shape]" in item.text()
            break

    assert tooltip is not None
    assert "tag: too-font-like" in tooltip
    assert "手書きよりフォント輪郭に寄っている" in tooltip
    legend_widget = window._reason_tag_legend_area.widget()
    assert legend_widget is not None
    labels = legend_widget.findChildren(QLabel)
    groups = legend_widget.findChildren(QGroupBox)
    assert any(label.text() == "Reason tag legend" for label in labels)
    assert any(group.title() == "motion" for group in groups)
    assert any(group.title() == "shape" for group in groups)

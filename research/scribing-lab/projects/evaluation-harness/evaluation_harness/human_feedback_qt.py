from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from evaluation_harness.human_feedback_common import (
    HumanFeedbackDraft,
    build_common_failure_examples,
    build_decision_help,
    build_review_instructions,
    choose_font_family,
    load_feedback_packet,
    load_response_drafts,
    serialize_response_drafts,
    validate_response_drafts,
)
from evaluation_harness.human_feedback_loop import ALLOWED_REASON_TAGS


DEFAULT_WINDOW_SIZE = (1760, 1120)
BODY_FONT_CANDIDATES: tuple[str, ...] = (
    "Noto Sans JP",
    "Noto Sans CJK JP",
    "Noto Sans",
    "DejaVu Sans",
    "Nimbus Sans",
    "URW Gothic",
    "Latin Modern Sans",
    "Helvetica",
)
MONO_FONT_CANDIDATES: tuple[str, ...] = (
    "Noto Sans Mono",
    "DejaVu Sans Mono",
    "Nimbus Mono PS",
    "Courier 10 Pitch",
    "Courier New",
    "Latin Modern Mono",
)


class PreviewLabel(QLabel):
    resized = Signal()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.resized.emit()


def _format_mapping(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _format_summary_lines(summary: dict[str, Any]) -> str:
    lines = [
        "Current action: review the selected item and decide whether it is acceptable.",
        f"decision_counts: {summary['decision_counts']}",
        f"missing_response_ids: {summary['missing_response_ids']}",
        f"unknown_response_ids: {summary['unknown_response_ids']}",
        f"duplicate_response_ids: {summary['duplicate_response_ids']}",
        f"validation_errors: {summary['validation_errors']}",
        f"can_proceed_to_plot: {summary['can_proceed_to_plot']}",
        "",
        "next_actions:",
    ]
    if summary["can_proceed_to_plot"]:
        lines.append("- plot-ready-packet を作成して plot 前確認へ進む")
    elif summary["validation_errors"]:
        lines.extend(f"- {item}" for item in summary["validation_errors"])
    else:
        lines.extend(
            [
                "- review rows を埋める",
                "- Validate で確認する",
                "- Export Responses で JSON を保存する",
            ]
        )
    return "\n".join(lines) + "\n"


class HumanFeedbackQtWindow(QMainWindow):
    def __init__(
        self,
        *,
        packet: dict[str, Any],
        drafts: dict[str, HumanFeedbackDraft],
        reviewer_id: str = "",
        responses_json_path: Path | None = None,
        summary_json_path: Path | None = None,
        base_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._packet = packet
        self._drafts = drafts
        self._reviewer_id = reviewer_id.strip()
        self._responses_json_path = responses_json_path
        self._summary_json_path = summary_json_path
        self._base_dir = base_dir or Path.cwd()
        self._current_experiment_id = self._first_experiment_id()
        self._preview_pixmap: QPixmap | None = None
        self._loading = False

        self.setWindowTitle("Human Feedback Loop")
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(1380, 900)

        self._configure_fonts()
        self._build_ui()
        self._refresh_all()

    def _configure_fonts(self) -> None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication is required before creating the UI")

        available = set(QFontDatabase.families())
        fallback_family = app.font().family()
        body_family = choose_font_family(available, BODY_FONT_CANDIDATES, fallback=fallback_family)
        mono_family = choose_font_family(available, MONO_FONT_CANDIDATES, fallback=fallback_family)

        body_font = QFont(body_family, 11)
        bold_font = QFont(body_font)
        heading_font = QFont(body_family, 18)
        mono_font = QFont(mono_family, 10)

        app.setFont(body_font)
        app.setStyle("Fusion")

        self.setFont(body_font)
        self._body_font = body_font
        self._body_bold_font = bold_font
        self._heading_font = heading_font
        self._mono_font = mono_font

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())
        root.addWidget(self._build_guide())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_summary_box())

        self.setCentralWidget(central)
        self.statusBar().showMessage("Select a representative to begin review.")

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Human Feedback Loop", header)
        title.setFont(self._heading_font)
        layout.addWidget(title, 0, Qt.AlignVCenter)
        layout.addStretch(1)

        reviewer_label = QLabel("Reviewer", header)
        reviewer_label.setFont(self._body_font)
        layout.addWidget(reviewer_label, 0, Qt.AlignVCenter)

        self._reviewer_edit = QLineEdit(header)
        self._reviewer_edit.setPlaceholderText("reviewer-id")
        self._reviewer_edit.setText(self._reviewer_id)
        self._reviewer_edit.setMinimumWidth(220)
        self._reviewer_edit.textChanged.connect(lambda _text: self._sync_from_widgets())
        layout.addWidget(self._reviewer_edit, 0, Qt.AlignVCenter)

        self._validate_button = QPushButton("Validate", header)
        self._validate_button.clicked.connect(self._validate_current)
        layout.addWidget(self._validate_button, 0, Qt.AlignVCenter)

        self._export_button = QPushButton("Export Responses", header)
        self._export_button.clicked.connect(self._export_responses)
        layout.addWidget(self._export_button, 0, Qt.AlignVCenter)

        self._refresh_button = QPushButton("Refresh Summary", header)
        self._refresh_button.clicked.connect(self._refresh_summary)
        layout.addWidget(self._refresh_button, 0, Qt.AlignVCenter)

        return header

    def _build_guide(self) -> QGroupBox:
        group = QGroupBox("How to review", self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        layout.addWidget(self._build_guide_column("Review steps", build_review_instructions()))
        layout.addWidget(self._build_guide_column("Decision hints", build_decision_help() + [""] + build_common_failure_examples()))
        return group

    def _build_guide_column(self, title: str, lines: list[str]) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_label = QLabel(title, widget)
        title_label.setFont(self._body_font)
        layout.addWidget(title_label)

        body = QLabel("\n".join(lines), widget)
        body.setFont(self._body_font)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setStyleSheet("color: #222;")
        layout.addWidget(body)
        layout.addStretch(1)
        return widget

    def _build_body(self) -> QWidget:
        body = QWidget(self)
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        left_panel = self._build_representatives_panel()
        right_panel = self._build_detail_panel()
        layout.addWidget(left_panel, 0)
        layout.addWidget(right_panel, 1)
        return body

    def _build_representatives_panel(self) -> QGroupBox:
        group = QGroupBox("Representatives", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._item_list = QListWidget(group)
        self._item_list.setFont(self._body_font)
        self._item_list.setMinimumWidth(340)
        self._item_list.currentRowChanged.connect(self._on_select_item)
        layout.addWidget(self._item_list, 1)

        for item in self._packet.get("representatives", []):
            label = f"{item['experiment_id']} | {item['input_text']} | seed={item['seed']}"
            list_item = QListWidgetItem(label)
            list_item.setToolTip(
                f"{item['experiment_id']}\ninput_text: {item['input_text']}\nseed: {item['seed']}"
            )
            self._item_list.addItem(list_item)

        return group

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        content_layout.addWidget(self._build_preview_box())
        content_layout.addWidget(self._build_details_box())
        content_layout.addWidget(self._build_decision_box())
        content_layout.addWidget(self._build_reason_tags_box())
        content_layout.addWidget(self._build_notes_box())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return panel

    def _build_preview_box(self) -> QGroupBox:
        group = QGroupBox("Preview", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._preview_label = PreviewLabel(group)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumHeight(360)
        self._preview_label.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #bcbcbc; color: #444; }"
        )
        self._preview_label.resized.connect(self._update_preview_pixmap)
        layout.addWidget(self._preview_label)
        return group

    def _build_details_box(self) -> QGroupBox:
        group = QGroupBox("Details", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._detail_text = QPlainTextEdit(group)
        self._detail_text.setReadOnly(True)
        self._detail_text.setFont(self._mono_font)
        self._detail_text.setMinimumHeight(220)
        layout.addWidget(self._detail_text)
        return group

    def _build_decision_box(self) -> QGroupBox:
        group = QGroupBox("Decision", self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._decision_group = QButtonGroup(group)
        self._decision_group.setExclusive(True)
        self._decision_buttons: dict[str, QRadioButton] = {}
        for decision in ("accept", "reject", "needs-tuning"):
            button = QRadioButton(decision, group)
            button.setFont(self._body_font)
            self._decision_group.addButton(button)
            layout.addWidget(button)
            self._decision_buttons[decision] = button
            button.toggled.connect(lambda _checked=False: self._sync_from_widgets())
        layout.addStretch(1)
        return group

    def _build_reason_tags_box(self) -> QGroupBox:
        group = QGroupBox("Reason Tags", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._reason_tags_list = QListWidget(group)
        self._reason_tags_list.setFont(self._body_font)
        self._reason_tags_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for tag in ALLOWED_REASON_TAGS:
            self._reason_tags_list.addItem(QListWidgetItem(tag))
        self._reason_tags_list.itemSelectionChanged.connect(self._sync_from_widgets)
        layout.addWidget(self._reason_tags_list)
        return group

    def _build_notes_box(self) -> QGroupBox:
        group = QGroupBox("Notes", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._notes_text = QPlainTextEdit(group)
        self._notes_text.setFont(self._body_font)
        self._notes_text.setPlaceholderText("Optional note for this review item.")
        self._notes_text.textChanged.connect(self._sync_from_widgets)
        self._notes_text.setMinimumHeight(150)
        layout.addWidget(self._notes_text)
        return group

    def _build_summary_box(self) -> QGroupBox:
        group = QGroupBox("Validation Summary", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._summary_text = QPlainTextEdit(group)
        self._summary_text.setReadOnly(True)
        self._summary_text.setFont(self._mono_font)
        self._summary_text.setMinimumHeight(180)
        layout.addWidget(self._summary_text)
        return group

    def _first_experiment_id(self) -> str:
        representatives = self._packet.get("representatives", [])
        if not representatives:
            return ""
        return str(representatives[0]["experiment_id"])

    def _current_draft(self) -> HumanFeedbackDraft | None:
        if not self._current_experiment_id:
            return None
        return self._drafts[self._current_experiment_id]

    def _current_item(self) -> dict[str, Any] | None:
        for item in self._packet.get("representatives", []):
            if str(item["experiment_id"]) == self._current_experiment_id:
                return item
        return None

    def _on_select_item(self, row: int) -> None:
        if row < 0:
            return
        self._capture_current_draft()
        item = self._packet.get("representatives", [])[row]
        self._current_experiment_id = str(item["experiment_id"])
        self._load_current_item()
        self.statusBar().showMessage(f"Selected {self._current_experiment_id}")

    def _load_current_item(self) -> None:
        item = self._current_item()
        draft = self._current_draft()
        if item is None or draft is None:
            return

        self._loading = True
        try:
            with QSignalBlocker(self._reviewer_edit):
                self._reviewer_edit.setText(draft.reviewer_id or self._reviewer_id)
            for decision, button in self._decision_buttons.items():
                with QSignalBlocker(button):
                    button.setChecked(draft.decision == decision)
            with QSignalBlocker(self._reason_tags_list):
                self._reason_tags_list.clearSelection()
                selected = set(draft.reason_tags)
                for index in range(self._reason_tags_list.count()):
                    item_tag = self._reason_tags_list.item(index).text()
                    self._reason_tags_list.item(index).setSelected(item_tag in selected)
            with QSignalBlocker(self._notes_text):
                self._notes_text.setPlainText(draft.notes)

            self._detail_text.setPlainText(self._render_detail_text(item))
            self._set_preview_image(item.get("preview", ""))
        finally:
            self._loading = False

    def _render_detail_text(self, item: dict[str, Any]) -> str:
        lines = [
            f"experiment_id: {item['experiment_id']}",
            f"input_text: {item['input_text']}",
            f"seed: {item['seed']}",
            f"reason: {item['reason']}",
            f"failure_tags: {item['failure_tags']}",
            "metrics:",
            _format_mapping(item["metrics"]),
        ]
        return "\n".join(lines)

    def _set_preview_image(self, path_text: str) -> None:
        self._preview_pixmap = None
        if not path_text:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("preview unavailable")
            return

        path = self._resolve_preview_path(path_text)
        if path is None or not path.exists():
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText(f"preview unavailable\n{path_text}")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText(f"failed to load preview\n{path_text}")
            return

        self._preview_pixmap = pixmap
        self._preview_label.setText("")
        self._update_preview_pixmap()

    def _resolve_preview_path(self, path_text: str) -> Path | None:
        path = Path(path_text)
        if path.exists():
            return path
        if not path.is_absolute():
            candidate = self._base_dir / path
            if candidate.exists():
                return candidate
        return path

    def _update_preview_pixmap(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        target = self._preview_label.size()
        if target.width() <= 0 or target.height() <= 0:
            target_width, target_height = 760, 420
        else:
            target_width, target_height = target.width() - 16, target.height() - 16
        scaled = self._preview_pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _selected_reason_tags(self) -> list[str]:
        return [
            self._reason_tags_list.item(index).text()
            for index in range(self._reason_tags_list.count())
            if self._reason_tags_list.item(index).isSelected()
        ]

    def _current_decision(self) -> str:
        for decision, button in self._decision_buttons.items():
            if button.isChecked():
                return decision
        return ""

    def _capture_current_draft(self) -> None:
        if self._loading:
            return
        self._apply_reviewer_id_to_all_drafts()
        draft = self._current_draft()
        if draft is None:
            return
        draft.decision = self._current_decision()
        draft.reason_tags = self._selected_reason_tags()
        draft.notes = self._notes_text.toPlainText().strip()
        draft.reviewer_id = self._reviewer_edit.text().strip()

    def _sync_from_widgets(self) -> None:
        if self._loading:
            return
        self._capture_current_draft()
        self._refresh_summary()

    def _apply_reviewer_id_to_all_drafts(self) -> None:
        reviewer_id = self._reviewer_edit.text().strip()
        for draft in self._drafts.values():
            draft.reviewer_id = reviewer_id

    def _current_rows(self) -> list[dict[str, Any]]:
        self._capture_current_draft()
        return [draft.to_dict() for draft in self._drafts.values()]

    def _refresh_all(self) -> None:
        if self._item_list.count() > 0:
            self._item_list.setCurrentRow(0)
        else:
            self._refresh_summary()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        self._summary_text.setPlainText(_format_summary_lines(summary))

    def _validate_current(self) -> None:
        self._refresh_summary()
        summary = validate_response_drafts(self._packet, self._drafts)
        if summary["validation_errors"]:
            QMessageBox.warning(
                self,
                "Human Feedback Loop",
                "Validation errors found. See summary.",
            )
        else:
            QMessageBox.information(self, "Human Feedback Loop", "Validation passed.")

    def _export_responses(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        self._summary_text.setPlainText(_format_summary_lines(summary))
        if summary["validation_errors"]:
            QMessageBox.warning(
                self,
                "Human Feedback Loop",
                "Responses are not complete yet. Fix validation errors before exporting.",
            )
            return

        output_path = self._responses_json_path or Path("human_review_responses.json")
        summary_path = self._summary_json_path or output_path.with_name("human_review_response_summary.json")
        response_payload = serialize_response_drafts(self._drafts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(response_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved responses to {output_path} and summary to {summary_path}",
        )


def launch_human_feedback_ui(
    *,
    root: Path | None = None,
    packet_json: Path | None = None,
    responses_json: Path | None = None,
    summary_json: Path | None = None,
    reviewer_id: str = "",
) -> None:
    base_dir = root or (packet_json.parent if packet_json is not None else Path.cwd())
    responses_path = responses_json or (base_dir / "human_review_responses.json")
    summary_path = summary_json or (base_dir / "human_review_response_summary.json")
    packet = load_feedback_packet(root=root, packet_json=packet_json)
    drafts = load_response_drafts(
        packet=packet,
        responses_json=responses_path if responses_path.exists() else None,
        reviewer_id=reviewer_id,
    )

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    window = HumanFeedbackQtWindow(
        packet=packet,
        drafts=drafts,
        reviewer_id=reviewer_id,
        responses_json_path=responses_path,
        summary_json_path=summary_path,
        base_dir=base_dir,
    )
    window.show()
    app.exec()

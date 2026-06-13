from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from evaluation_harness.human_feedback_common import (
    HumanFeedbackDraft,
    choose_font_family,
    load_feedback_packet,
    load_response_drafts,
    render_review_guide_markdown,
    serialize_response_drafts,
    validate_response_drafts,
)
from evaluation_harness.compare import propose_preview_fixed_input_set
from evaluation_harness.human_feedback_loop import ALLOWED_REASON_TAGS
from evaluation_harness.human_review_response import (
    build_human_review_start_card,
    build_human_review_comparison_sheet,
    build_human_review_prompt,
    build_human_review_revision_brief,
    build_human_review_preview_revision_plan,
    build_human_review_revision_plan,
    render_human_review_start_card_markdown,
    render_human_review_comparison_sheet_markdown,
    render_human_review_prompt_markdown,
    render_human_review_revision_brief_markdown,
    render_human_review_preview_revision_plan_markdown,
    render_human_review_revision_plan_markdown,
)
from evaluation_harness.human_review import render_human_review_packet_markdown
from evaluation_harness.evaluation_inputs import get_evaluation_inputs
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.revision_loop import (
    render_preview_revision_loop_markdown,
    run_preview_revision_loop_fixed_input_set,
)
from evaluation_harness.taxonomy import describe_failure_tag, failure_tag_group


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


class PreviewView(QGraphicsView):
    zoomRequested = Signal(float)
    WHEEL_STEP = 1.08
    MIN_ZOOM = 0.2
    MAX_ZOOM = 12.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

    def viewportEvent(self, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Wheel:
            wheel_event = event  # QWheelEvent
            pixel_delta = wheel_event.pixelDelta().y()
            angle_delta = wheel_event.angleDelta().y()
            delta = pixel_delta if pixel_delta else angle_delta
            if delta:
                self.zoomRequested.emit(self.WHEEL_STEP ** (delta / 120.0))
                return True
        return super().viewportEvent(event)


def _format_mapping(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _format_summary_lines(summary: dict[str, Any]) -> str:
    lines = [
        "Current action: review the selected item and decide whether it is acceptable.",
        f"decision_counts: {summary['decision_counts']}",
        f"note_count: {summary.get('note_count', 0)}",
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
        sort_order: str = "default",
        responses_json_path: Path | None = None,
        summary_json_path: Path | None = None,
        brief_json_path: Path | None = None,
        brief_markdown_path: Path | None = None,
        plan_json_path: Path | None = None,
        plan_markdown_path: Path | None = None,
        packet_json_path: Path | None = None,
        packet_markdown_path: Path | None = None,
        start_card_json_path: Path | None = None,
        start_card_markdown_path: Path | None = None,
        comparison_sheet_json_path: Path | None = None,
        comparison_sheet_markdown_path: Path | None = None,
        prompt_json_path: Path | None = None,
        prompt_markdown_path: Path | None = None,
        preview_run_json_path: Path | None = None,
        preview_run_markdown_path: Path | None = None,
        initial_detail_tab: str = "start-card",
        base_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._packet = packet
        self._drafts = drafts
        self._reviewer_id = reviewer_id.strip()
        self._sort_order = str(packet.get("sort_order", sort_order) or "default")
        self._responses_json_path = responses_json_path
        self._summary_json_path = summary_json_path
        self._brief_json_path = brief_json_path
        self._brief_markdown_path = brief_markdown_path
        self._plan_json_path = plan_json_path
        self._plan_markdown_path = plan_markdown_path
        self._packet_json_path = packet_json_path
        self._packet_markdown_path = packet_markdown_path
        self._start_card_json_path = start_card_json_path
        self._start_card_markdown_path = start_card_markdown_path
        self._comparison_sheet_json_path = comparison_sheet_json_path
        self._comparison_sheet_markdown_path = comparison_sheet_markdown_path
        self._prompt_json_path = prompt_json_path
        self._prompt_markdown_path = prompt_markdown_path
        self._preview_run_json_path = preview_run_json_path
        self._preview_run_markdown_path = preview_run_markdown_path
        self._initial_detail_tab = initial_detail_tab
        self._base_dir = base_dir or Path.cwd()
        self._current_experiment_id = self._first_experiment_id()
        self._preview_pixmap: QPixmap | None = None
        self._preview_zoom = 1.6
        self._applied_preview_zoom = 1.0
        self._loading = False
        self._preview_dragging = False
        self._preview_last_pan_pos = None

        self.setWindowTitle(f"Human Feedback Loop [{self._sort_order}]")
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
        root.addWidget(self._build_body(), 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage(
            f"Select a representative to begin review. sort_order={self._sort_order}"
        )

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

        self._brief_button = QPushButton("Export Brief", header)
        self._brief_button.clicked.connect(self._export_revision_brief)
        layout.addWidget(self._brief_button, 0, Qt.AlignVCenter)

        self._plan_button = QPushButton("Export Plan", header)
        self._plan_button.clicked.connect(self._export_revision_plan)
        layout.addWidget(self._plan_button, 0, Qt.AlignVCenter)

        self._preview_plan_button = QPushButton("Refresh Preview Plan", header)
        self._preview_plan_button.clicked.connect(self._refresh_preview_plan)
        layout.addWidget(self._preview_plan_button, 0, Qt.AlignVCenter)

        self._packet_button = QPushButton("Export Packet", header)
        self._packet_button.clicked.connect(self._export_packet_bundle)
        layout.addWidget(self._packet_button, 0, Qt.AlignVCenter)

        self._start_card_button = QPushButton("Export Start Card", header)
        self._start_card_button.clicked.connect(self._export_start_card)
        layout.addWidget(self._start_card_button, 0, Qt.AlignVCenter)

        self._bundle_button = QPushButton("Export Review Bundle", header)
        self._bundle_button.clicked.connect(self._export_review_bundle)
        layout.addWidget(self._bundle_button, 0, Qt.AlignVCenter)

        self._preview_run_button = QPushButton("Export Preview Run", header)
        self._preview_run_button.clicked.connect(self._export_preview_revision_run)
        layout.addWidget(self._preview_run_button, 0, Qt.AlignVCenter)

        self._refresh_button = QPushButton("Refresh Summary", header)
        self._refresh_button.clicked.connect(self._refresh_summary)
        layout.addWidget(self._refresh_button, 0, Qt.AlignVCenter)

        self._guide_button = QPushButton("Review Guide", header)
        self._guide_button.clicked.connect(self._show_review_guide)
        layout.addWidget(self._guide_button, 0, Qt.AlignVCenter)

        return header

    def _show_review_guide(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Review Guide")
        dialog.setMinimumSize(920, 660)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        body = QPlainTextEdit(dialog)
        body.setReadOnly(True)
        body.setFont(self._body_font)
        body.setPlainText(self._build_review_guide_text())
        layout.addWidget(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _build_review_guide_text(self) -> str:
        return render_review_guide_markdown()

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
            script_groups = ",".join(item.get("input_script_groups", [])) or "other"
            label = (
                f"{item['experiment_id']} | {item['input_text']} | "
                f"groups={script_groups} | seed={item['seed']}"
            )
            list_item = QListWidgetItem(label)
            list_item.setToolTip(
                f"{item['experiment_id']}\ninput_text: {item['input_text']}\n"
                f"input_script_groups: {item.get('input_script_groups', [])}\nseed: {item['seed']}"
            )
            self._item_list.addItem(list_item)

        return group

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, panel)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_preview_box())
        splitter.addWidget(self._build_detail_tabs())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(12)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout.addWidget(splitter, 1)
        return panel

    def _build_preview_box(self) -> QGroupBox:
        group = QGroupBox("Preview", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        controls = QWidget(group)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        fit_button = QPushButton("Fit", controls)
        fit_button.clicked.connect(self._fit_preview_to_window)
        controls_layout.addWidget(fit_button)

        zoom_out_button = QPushButton("Zoom -", controls)
        zoom_out_button.clicked.connect(lambda: self._set_preview_zoom(self._preview_zoom / 1.2))
        controls_layout.addWidget(zoom_out_button)

        zoom_in_button = QPushButton("Zoom +", controls)
        zoom_in_button.clicked.connect(lambda: self._set_preview_zoom(self._preview_zoom * 1.2))
        controls_layout.addWidget(zoom_in_button)

        zoom_reset_button = QPushButton("1x", controls)
        zoom_reset_button.clicked.connect(lambda: self._set_preview_zoom(1.0))
        controls_layout.addWidget(zoom_reset_button)

        controls_layout.addStretch(1)
        layout.addWidget(controls)

        self._preview_scene = QGraphicsScene(self)
        self._preview_view = PreviewView(group)
        self._preview_view.setScene(self._preview_scene)
        self._preview_view.zoomRequested.connect(self._adjust_preview_zoom)
        self._preview_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_view.setMinimumHeight(820)
        self._preview_view.setMinimumWidth(760)
        layout.addWidget(self._preview_view)
        return group

    def _build_detail_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        self._detail_tabs = tabs
        tabs.setMinimumWidth(360)
        tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        tabs.addTab(self._build_start_card_box(), "Start Card")
        tabs.addTab(self._build_comparison_sheet_box(), "Comparison Sheet")
        tabs.addTab(self._build_prompt_box(), "Review Prompt")
        tabs.addTab(self._build_details_box(), "Details")
        tabs.addTab(self._build_review_box(), "Review")
        tabs.addTab(self._build_notes_box(), "Notes")
        tabs.addTab(self._build_brief_box(), "Brief")
        tabs.addTab(self._build_plan_box(), "Plan")
        tabs.addTab(self._build_preview_run_box(), "Preview Run")
        return tabs

    def _build_review_box(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_decision_box())
        layout.addWidget(self._build_reason_tags_box())
        layout.addStretch(1)
        return widget

    def _build_start_card_box(self) -> QGroupBox:
        group = QGroupBox("Start Card", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._start_card_text = QPlainTextEdit(group)
        self._start_card_text.setReadOnly(True)
        self._start_card_text.setFont(self._body_font)
        layout.addWidget(self._start_card_text)
        return group

    def _build_comparison_sheet_box(self) -> QGroupBox:
        group = QGroupBox("Comparison Sheet", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._comparison_sheet_text = QPlainTextEdit(group)
        self._comparison_sheet_text.setReadOnly(True)
        self._comparison_sheet_text.setFont(self._body_font)
        layout.addWidget(self._comparison_sheet_text)
        return group

    def _build_prompt_box(self) -> QGroupBox:
        group = QGroupBox("Review Prompt", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._prompt_text = QPlainTextEdit(group)
        self._prompt_text.setReadOnly(True)
        self._prompt_text.setFont(self._body_font)
        layout.addWidget(self._prompt_text)
        return group

    def _build_details_box(self) -> QGroupBox:
        group = QGroupBox("Details", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._detail_text = QPlainTextEdit(group)
        self._detail_text.setReadOnly(True)
        self._detail_text.setFont(self._mono_font)
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
        layout.setSpacing(8)

        self._reason_tags_list = QListWidget(group)
        self._reason_tags_list.setFont(self._body_font)
        self._reason_tags_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for tag in ALLOWED_REASON_TAGS:
            item = QListWidgetItem(self._reason_tag_list_label(tag))
            item.setToolTip(self._reason_tag_tooltip(tag))
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self._reason_tags_list.addItem(item)
        self._reason_tags_list.itemSelectionChanged.connect(self._sync_from_widgets)
        layout.addWidget(self._reason_tags_list)

        self._reason_tag_legend_area = QScrollArea(group)
        self._reason_tag_legend_area.setWidgetResizable(True)
        self._reason_tag_legend_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._reason_tag_legend_area.setMinimumHeight(210)
        self._reason_tag_legend_area.setMaximumHeight(280)
        self._reason_tag_legend_area.setWidget(self._build_reason_tag_legend_widget())
        layout.addWidget(self._reason_tag_legend_area)
        return group

    def _build_notes_box(self) -> QGroupBox:
        group = QGroupBox("Notes", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._notes_text = QPlainTextEdit(group)
        self._notes_text.setFont(self._body_font)
        self._notes_text.setPlaceholderText("Optional note for this review item.")
        self._notes_text.textChanged.connect(self._sync_from_widgets)
        layout.addWidget(self._notes_text)
        return group

    def _build_brief_box(self) -> QGroupBox:
        group = QGroupBox("Revision Brief", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._brief_text = QPlainTextEdit(group)
        self._brief_text.setReadOnly(True)
        self._brief_text.setFont(self._body_font)
        layout.addWidget(self._brief_text)
        return group

    def _build_plan_box(self) -> QGroupBox:
        group = QGroupBox("Revision Plan", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._plan_text = QPlainTextEdit(group)
        self._plan_text.setReadOnly(True)
        self._plan_text.setFont(self._body_font)
        layout.addWidget(self._plan_text)
        return group

    def _build_preview_run_box(self) -> QGroupBox:
        group = QGroupBox("Preview Run", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        self._preview_run_text = QPlainTextEdit(group)
        self._preview_run_text.setReadOnly(True)
        self._preview_run_text.setFont(self._body_font)
        layout.addWidget(self._preview_run_text)
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

    def _reason_tag_tooltip(self, tag: str) -> str:
        description = describe_failure_tag(tag) or "説明なし"
        group = failure_tag_group(tag)
        return "\n".join(
            [
                f"tag: {tag}",
                f"group: {group}",
                f"description: {description}",
            ]
        )

    def _reason_tag_list_label(self, tag: str) -> str:
        group = failure_tag_group(tag)
        description = describe_failure_tag(tag) or "説明なし"
        short_description = description.rstrip("。")
        return f"{tag}  [{group}]  - {short_description}"

    def _build_reason_tag_legend_widget(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Reason tag legend", widget)
        title.setFont(self._body_bold_font)
        layout.addWidget(title)

        for group_name, tags in self._reason_tag_groups().items():
            card = QGroupBox(group_name, widget)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(6)

            for tag in tags:
                tag_label = QLabel(self._reason_tag_summary_text(tag), card)
                tag_label.setWordWrap(True)
                tag_label.setFont(self._body_font)
                tag_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                card_layout.addWidget(tag_label)

            layout.addWidget(card)

        layout.addStretch(1)
        return widget

    def _reason_tag_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for tag in ALLOWED_REASON_TAGS:
            groups.setdefault(failure_tag_group(tag), []).append(tag)
        return {group: sorted(tags) for group, tags in sorted(groups.items())}

    def _reason_tag_summary_text(self, tag: str) -> str:
        description = describe_failure_tag(tag) or "説明なし"
        return "\n".join(
            [
                f"{tag}: {description}",
                f"  use: {self._reason_tag_use_hint(tag)}",
            ]
        )

    def _reason_tag_use_hint(self, tag: str) -> str:
        hints = {
            "too-small": "文字が小さくて読みにくいとき。",
            "glyph-orientation-odd": "文字や部品の向きが変に見えるとき。",
            "spacing-too-wide": "字間や余白が広すぎるとき。",
            "spacing-unnatural": "配置や行間の揺れが不自然なとき。",
            "skeleton-too-rigid": "骨格が硬すぎて変化がないとき。",
            "too-font-like": "手書きよりフォントっぽいとき。",
            "too-uniform": "速度や形が均一すぎて機械的なとき。",
            "line-too-mechanical": "行全体が機械的に整いすぎているとき。",
            "terminal-too-uniform": "終筆の抜きに差が少ないとき。",
            "repeated-char-too-identical": "反復文字が同じ形に寄りすぎるとき。",
            "over-jittered": "揺れが強すぎて荒れて見えるとき。",
            "plotter-unsafe": "実機制約に対して危険なとき。",
        }
        return hints.get(tag, "該当する見え方があるとき。")

    def _on_select_item(self, row: int) -> None:
        if row < 0:
            return
        self._capture_current_draft()
        item = self._packet.get("representatives", [])[row]
        self._current_experiment_id = str(item["experiment_id"])
        self._load_current_item()
        self.statusBar().showMessage(
            f"sort_order={self._sort_order} | Selected {self._current_experiment_id}"
        )

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
                    tag_item = self._reason_tags_list.item(index)
                    item_tag = str(tag_item.data(Qt.ItemDataRole.UserRole) or tag_item.text())
                    tag_item.setSelected(item_tag in selected)
            with QSignalBlocker(self._notes_text):
                self._notes_text.setPlainText(draft.notes)

            self._detail_text.setPlainText(self._render_detail_text(item))
            self._set_preview_image(item.get("preview", ""))
            self._refresh_preview_plan()
        finally:
            self._loading = False

    def _render_detail_text(self, item: dict[str, Any]) -> str:
        lines = [
            f"experiment_id: {item['experiment_id']}",
            f"input_text: {item['input_text']}",
            f"input_script_groups: {item.get('input_script_groups', [])}",
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
            self._preview_scene.clear()
            self._preview_scene.setSceneRect(0, 0, 0, 0)
            return

        path = self._resolve_preview_path(path_text)
        if path is None or not path.exists():
            self._preview_scene.clear()
            self._preview_scene.setSceneRect(0, 0, 0, 0)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._preview_scene.clear()
            self._preview_scene.setSceneRect(0, 0, 0, 0)
            return

        self._preview_pixmap = pixmap
        self._preview_scene.clear()
        self._preview_pixmap_item = QGraphicsPixmapItem(self._preview_pixmap)
        self._preview_scene.addItem(self._preview_pixmap_item)
        self._preview_scene.setSceneRect(self._preview_pixmap_item.boundingRect())
        self._applied_preview_zoom = 1.0
        self._fit_preview_to_window()

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
        if not hasattr(self, "_preview_pixmap_item"):
            return
        factor = self._preview_zoom / max(self._applied_preview_zoom, 1e-9)
        if factor == 1.0:
            return
        self._preview_view.scale(factor, factor)
        self._applied_preview_zoom = self._preview_zoom

    def _adjust_preview_zoom(self, factor: float) -> None:
        self._set_preview_zoom(self._preview_zoom * factor)

    def _set_preview_zoom(self, zoom: float, *, reset_view: bool = False) -> None:
        self._preview_zoom = max(PreviewView.MIN_ZOOM, min(PreviewView.MAX_ZOOM, zoom))
        if reset_view:
            self._preview_view.resetTransform()
            self._preview_view.centerOn(self._preview_pixmap_item)
            self._applied_preview_zoom = 1.0
        self._update_preview_pixmap()

    def _fit_preview_to_window(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        viewport = self._preview_view.viewport().size()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        pixmap_width = max(self._preview_pixmap.width(), 1)
        pixmap_height = max(self._preview_pixmap.height(), 1)
        fit_zoom = min(
            (viewport.width() - 16) / pixmap_width,
            (viewport.height() - 16) / pixmap_height,
        )
        self._set_preview_zoom(max(0.5, fit_zoom), reset_view=True)

    def _selected_reason_tags(self) -> list[str]:
        return [
            str(self._reason_tags_list.item(index).data(Qt.ItemDataRole.UserRole) or self._reason_tags_list.item(index).text())
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
        self._refresh_start_card()
        self._refresh_comparison_sheet()
        self._refresh_prompt()
        self._refresh_revision_brief()
        self._refresh_revision_plan()

    def _apply_reviewer_id_to_all_drafts(self) -> None:
        reviewer_id = self._reviewer_edit.text().strip()
        for draft in self._drafts.values():
            draft.reviewer_id = reviewer_id

    def _current_rows(self) -> list[dict[str, Any]]:
        self._capture_current_draft()
        return [draft.to_dict() for draft in self._drafts.values()]

    def _refresh_all(self) -> None:
        if self._item_list.count() > 0:
            self._loading = True
            try:
                self._item_list.setCurrentRow(0)
            finally:
                self._loading = False
        else:
            self._refresh_summary()
        if hasattr(self, "_detail_tabs"):
            self._detail_tabs.setCurrentIndex(self._detail_tab_index(self._initial_detail_tab))
        self._refresh_summary()
        self._refresh_start_card()
        self._refresh_comparison_sheet()
        self._refresh_prompt()
        self._refresh_revision_brief()
        self._refresh_revision_plan()
        self._refresh_preview_plan()

    def _detail_tab_index(self, tab_name: str) -> int:
        tab_order = [
            "start-card",
            "comparison-sheet",
            "review-prompt",
            "details",
            "review",
            "notes",
            "brief",
            "plan",
            "preview-run",
        ]
        try:
            return tab_order.index(tab_name)
        except ValueError:
            return 0

    def _refresh_summary(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        self.statusBar().showMessage(
            " | ".join(
                [
                    f"sort_order={self._sort_order}",
                    f"decisions={summary['decision_counts']}",
                    f"notes={summary.get('note_count', 0)}",
                    f"missing={len(summary['missing_response_ids'])}",
                    f"duplicates={len(summary['duplicate_response_ids'])}",
                    f"can_proceed={summary['can_proceed_to_plot']}",
                ]
            )
        )

    def _current_start_card(self) -> dict[str, Any]:
        summary = validate_response_drafts(self._packet, self._drafts)
        return build_human_review_start_card(self._packet, summary, sort_order=self._sort_order)

    def _refresh_start_card(self) -> None:
        if not hasattr(self, "_start_card_text"):
            return
        self._start_card_text.setPlainText(
            render_human_review_start_card_markdown(self._current_start_card())
        )

    def _current_comparison_sheet(self) -> dict[str, Any]:
        return build_human_review_comparison_sheet(self._packet)

    def _refresh_comparison_sheet(self) -> None:
        if not hasattr(self, "_comparison_sheet_text"):
            return
        self._comparison_sheet_text.setPlainText(
            render_human_review_comparison_sheet_markdown(self._current_comparison_sheet())
        )

    def _current_prompt(self) -> dict[str, Any]:
        return build_human_review_prompt(self._packet)

    def _refresh_prompt(self) -> None:
        if not hasattr(self, "_prompt_text"):
            return
        self._prompt_text.setPlainText(render_human_review_prompt_markdown(self._current_prompt()))

    def _current_revision_brief(self) -> dict[str, Any]:
        summary = validate_response_drafts(self._packet, self._drafts)
        return build_human_review_revision_brief(summary)

    def _refresh_revision_brief(self) -> None:
        if not hasattr(self, "_brief_text"):
            return
        brief = self._current_revision_brief()
        self._brief_text.setPlainText(render_human_review_revision_brief_markdown(brief))

    def _current_revision_plan(self) -> dict[str, Any]:
        brief = self._current_revision_brief()
        return build_human_review_revision_plan(brief)

    def _refresh_revision_plan(self) -> None:
        if not hasattr(self, "_plan_text"):
            return
        plan = self._current_revision_plan()
        self._plan_text.setPlainText(render_human_review_revision_plan_markdown(plan))

    def _current_preview_revision_plan(self) -> dict[str, Any]:
        brief = self._current_revision_brief()
        expected_input_texts, expected_seeds = self._packet_preview_axes()
        registry = ExperimentRegistry(self._base_dir / "registry.jsonl")
        preview_proposal = propose_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator="baseline-outline",
            expected_input_texts=expected_input_texts,
            expected_seeds=expected_seeds,
        )
        return build_human_review_preview_revision_plan(brief, preview_proposal)

    def _refresh_preview_plan(self) -> None:
        if not hasattr(self, "_preview_run_text"):
            return
        preview_plan = self._current_preview_revision_plan()
        self._preview_run_text.setPlainText(
            "\n".join(
                [
                    "# Preview Run",
                    "",
                    f"- human_focus_area: `{preview_plan['human_focus_area']}`",
                    f"- preview_selected_candidate_count: `{preview_plan['preview_selected_candidate_count']}`",
                    f"- preview_focus_area_counts: `{preview_plan['preview_focus_area_counts']}`",
                    "",
                    "## Human Revision Plan",
                    "",
                    render_human_review_revision_plan_markdown(preview_plan["human_revision_plan"]),
                    "",
                    "## Preview Revision Plan",
                    "",
                    render_human_review_preview_revision_plan_markdown(preview_plan),
                ]
            )
        )

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
        self._write_revision_brief()
        self._write_revision_plan()
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved responses to {output_path} and summary to {summary_path}",
        )

    def _export_review_bundle(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        if summary["validation_errors"]:
            QMessageBox.warning(
                self,
                "Human Feedback Loop",
                "Review bundle requires valid responses. Fix validation errors before exporting.",
            )
            return

        packet = self._write_packet()
        start_card = self._write_start_card()
        comparison_sheet = self._write_comparison_sheet()
        prompt = self._write_prompt()
        responses = self._write_responses_and_summary(summary)
        brief = self._write_revision_brief()
        plan = self._write_revision_plan()
        preview_payload = self._current_preview_revision_run(summary=summary)
        preview_run = self._write_preview_revision_run(preview_payload)

        QMessageBox.information(
            self,
            "Human Feedback Loop",
            "Saved review bundle:\n"
            f"- packet: {packet['markdown']}\n"
            f"- start card: {start_card['markdown']}\n"
            f"- comparison sheet: {comparison_sheet['markdown']}\n"
            f"- review prompt: {prompt['markdown']}\n"
            f"- responses: {responses['responses']}\n"
            f"- summary: {responses['summary']}\n"
            f"- brief: {brief['markdown']}\n"
            f"- plan: {plan['markdown']}\n"
            f"- preview run: {preview_run['markdown']}",
        )

    def _export_packet_bundle(self) -> None:
        packet = self._write_packet()
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved packet to {packet['markdown']}",
        )

    def _export_start_card(self) -> None:
        card = self._write_start_card()
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved start card to {card['markdown']}",
        )

    def _export_revision_brief(self) -> None:
        self._write_revision_brief()
        self._write_revision_plan()
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved revision brief to {self._brief_markdown_path or self._default_brief_markdown_path()}",
        )

    def _export_revision_plan(self) -> None:
        self._write_revision_plan()
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved revision plan to {self._plan_markdown_path or self._default_plan_markdown_path()}",
        )

    def _export_preview_revision_run(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        if summary["validation_errors"]:
            QMessageBox.warning(
                self,
                "Human Feedback Loop",
                "Preview revision run requires valid responses. Fix validation errors first.",
            )
            return

        self._write_revision_brief()
        self._write_revision_plan()
        payload = self._current_preview_revision_run(summary=summary)
        self._write_preview_revision_run(payload)
        QMessageBox.information(
            self,
            "Human Feedback Loop",
            f"Saved preview revision run to {self._preview_run_markdown_path or self._default_preview_run_markdown_path()}",
        )

    def _write_responses_and_summary(self, summary: dict[str, Any]) -> dict[str, Path]:
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
        return {"responses": output_path, "summary": summary_path}

    def _write_packet(self) -> dict[str, Path]:
        markdown_path = self._packet_markdown_path or self._default_packet_markdown_path()
        json_path = self._packet_json_path or self._default_packet_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(self._render_packet_markdown(), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(self._packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _write_start_card(self) -> dict[str, Path]:
        card = self._current_start_card()
        markdown_path = self._start_card_markdown_path or self._default_start_card_markdown_path()
        json_path = self._start_card_json_path or self._default_start_card_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_human_review_start_card_markdown(card), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _write_comparison_sheet(self) -> dict[str, Path]:
        sheet = self._current_comparison_sheet()
        markdown_path = self._comparison_sheet_markdown_path or self._default_comparison_sheet_markdown_path()
        json_path = self._comparison_sheet_json_path or self._default_comparison_sheet_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_human_review_comparison_sheet_markdown(sheet), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(sheet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _write_prompt(self) -> dict[str, Path]:
        prompt = self._current_prompt()
        markdown_path = self._prompt_markdown_path or self._default_prompt_markdown_path()
        json_path = self._prompt_json_path or self._default_prompt_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_human_review_prompt_markdown(prompt), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(prompt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _render_packet_markdown(self) -> str:
        if "record_count" in self._packet and "representative_count" in self._packet:
            return render_human_review_packet_markdown(self._packet)

        lines = [
            "# Human Review Packet",
            "",
            f"- representative_count: `{len(self._packet.get('representatives', []))}`",
        ]
        if "records_by_input" in self._packet:
            lines.append(f"- records_by_input: `{self._packet['records_by_input']}`")
        lines.extend(["", "## Representatives", ""])
        representatives = self._packet.get("representatives", [])
        if not representatives:
            lines.append("- none")
        for item in representatives:
            lines.extend(
                [
                    f"### {item.get('experiment_id', 'unknown')}",
                    "",
                    f"- reason: `{item.get('reason', '')}`",
                    f"- input_text: `{item.get('input_text', '')}`",
                    f"- seed: `{item.get('seed', '')}`",
                    f"- preview: `{item.get('preview', '')}`",
                    f"- failure_tags: `{item.get('failure_tags', [])}`",
                    f"- metrics: `{item.get('metrics', {})}`",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"

    def _write_revision_brief(self) -> dict[str, Path]:
        brief = self._current_revision_brief()
        markdown_path = self._brief_markdown_path or self._default_brief_markdown_path()
        json_path = self._brief_json_path or self._default_brief_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_human_review_revision_brief_markdown(brief), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _write_revision_plan(self) -> dict[str, Path]:
        plan = self._current_revision_plan()
        markdown_path = self._plan_markdown_path or self._default_plan_markdown_path()
        json_path = self._plan_json_path or self._default_plan_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_human_review_revision_plan_markdown(plan), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _write_preview_revision_run(self, payload: dict[str, Any]) -> dict[str, Path]:
        run = payload["preview_revision_run"]
        markdown_path = self._preview_run_markdown_path or self._default_preview_run_markdown_path()
        json_path = self._preview_run_json_path or self._default_preview_run_json_path()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_preview_revision_loop_markdown(run), encoding="utf-8")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(
                {
                    "human_revision_plan": payload["human_revision_plan"],
                    "preview_revision_run": payload["preview_revision_run"],
                    "rerun_plan_count": payload["rerun_plan_count"],
                    "focus_areas": payload["focus_areas"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def _default_brief_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_revision_brief.md")
        return Path("human_review_revision_brief.md")

    def _default_brief_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_revision_brief.json")
        return Path("human_review_revision_brief.json")

    def _default_plan_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_revision_plan.md")
        return Path("human_review_revision_plan.md")

    def _default_plan_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_revision_plan.json")
        return Path("human_review_revision_plan.json")

    def _default_packet_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_packet.md")
        return Path("human_review_packet.md")

    def _default_packet_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_packet.json")
        return Path("human_review_packet.json")

    def _default_start_card_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_start_card.md")
        return Path("human_review_start_card.md")

    def _default_start_card_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_start_card.json")
        return Path("human_review_start_card.json")

    def _default_comparison_sheet_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_comparison_sheet.md")
        return Path("human_review_comparison_sheet.md")

    def _default_comparison_sheet_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_comparison_sheet.json")
        return Path("human_review_comparison_sheet.json")

    def _default_prompt_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_prompt.md")
        return Path("human_review_prompt.md")

    def _default_prompt_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_prompt.json")
        return Path("human_review_prompt.json")

    def _default_preview_run_markdown_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_preview_revision_run.md")
        return Path("human_review_preview_revision_run.md")

    def _default_preview_run_json_path(self) -> Path:
        if self._responses_json_path is not None:
            return self._responses_json_path.with_name("human_review_preview_revision_run.json")
        return Path("human_review_preview_revision_run.json")

    def _current_preview_revision_run(
        self,
        *,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if summary is None:
            self._capture_current_draft()
            summary = validate_response_drafts(self._packet, self._drafts)
        brief = build_human_review_revision_brief(summary)
        expected_input_texts, expected_seeds = self._packet_preview_axes()
        registry = ExperimentRegistry(self._base_dir / "registry.jsonl")
        preview_proposal = propose_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator="baseline-outline",
            expected_input_texts=expected_input_texts,
            expected_seeds=expected_seeds,
        )
        preview_plan = build_human_review_preview_revision_plan(brief, preview_proposal)
        preview_revision_plans = list(preview_plan.get("preview_revision_plans", []))
        run = run_preview_revision_loop_fixed_input_set(
            self._base_dir,
            expected_input_texts=expected_input_texts,
            expected_seeds=expected_seeds,
            baseline_generator="baseline-outline",
            revision_plans=preview_revision_plans,
        )
        return {
            "human_revision_plan": preview_plan,
            "preview_revision_run": run,
            "rerun_plan_count": len(preview_revision_plans),
            "expected_input_texts": list(expected_input_texts),
            "expected_seeds": list(expected_seeds),
            "focus_areas": sorted(
                {
                    str(plan.get("focus_area", "preview") or "preview")
                    for plan in preview_revision_plans
                }
            ),
        }

    def _packet_preview_axes(self) -> tuple[tuple[str, ...], tuple[int, ...]]:
        representatives = self._packet.get("representatives", [])
        input_texts = tuple(
            dict.fromkeys(
                str(item.get("input_text", ""))
                for item in representatives
                if str(item.get("input_text", "")).strip()
            )
        )
        seeds = tuple(
            dict.fromkeys(
                int(item.get("seed", 0))
                for item in representatives
                if str(item.get("seed", "")).strip()
            )
        )
        if not input_texts:
            input_texts = tuple(get_evaluation_inputs("wide"))
        if not seeds:
            seeds = (1, 2, 3)
        return input_texts, seeds


def launch_human_feedback_ui(
    *,
    root: Path | None = None,
    packet_json: Path | None = None,
    responses_json: Path | None = None,
    summary_json: Path | None = None,
    brief_json: Path | None = None,
    brief_markdown: Path | None = None,
    plan_json: Path | None = None,
    plan_markdown: Path | None = None,
    packet_output_json: Path | None = None,
    packet_output_markdown: Path | None = None,
    start_card_json: Path | None = None,
    start_card_markdown: Path | None = None,
    comparison_sheet_json: Path | None = None,
    comparison_sheet_markdown: Path | None = None,
    prompt_json: Path | None = None,
    prompt_markdown: Path | None = None,
    preview_run_json: Path | None = None,
    preview_run_markdown: Path | None = None,
    reviewer_id: str = "",
    target_count: int | None = None,
    sort_order: str = "default",
    initial_detail_tab: str = "start-card",
) -> None:
    base_dir = root or (packet_json.parent if packet_json is not None else Path.cwd())
    responses_path = responses_json or (base_dir / "human_review_responses.json")
    summary_path = summary_json or (base_dir / "human_review_response_summary.json")
    brief_json_path = brief_json or (base_dir / "human_review_revision_brief.json")
    brief_markdown_path = brief_markdown or (base_dir / "human_review_revision_brief.md")
    plan_json_path = plan_json or (base_dir / "human_review_revision_plan.json")
    plan_markdown_path = plan_markdown or (base_dir / "human_review_revision_plan.md")
    packet_json_path = packet_output_json or (base_dir / "human_review_packet.json")
    packet_markdown_path = packet_output_markdown or (base_dir / "human_review_packet.md")
    start_card_json_path = start_card_json or (base_dir / "human_review_start_card.json")
    start_card_markdown_path = start_card_markdown or (base_dir / "human_review_start_card.md")
    comparison_sheet_json_path = comparison_sheet_json or (base_dir / "human_review_comparison_sheet.json")
    comparison_sheet_markdown_path = (
        comparison_sheet_markdown or (base_dir / "human_review_comparison_sheet.md")
    )
    prompt_json_path = prompt_json or (base_dir / "human_review_prompt.json")
    prompt_markdown_path = prompt_markdown or (base_dir / "human_review_prompt.md")
    preview_run_json_path = preview_run_json or (base_dir / "human_review_preview_revision_run.json")
    preview_run_markdown_path = preview_run_markdown or (base_dir / "human_review_preview_revision_run.md")
    packet = load_feedback_packet(
        root=root,
        packet_json=packet_json,
        target_count=target_count,
        sort_order=sort_order,
    )
    if initial_detail_tab == "start-card" and packet_json is not None and root is not None and packet_json.name.endswith("_packet.json"):
        initial_detail_tab = "comparison-sheet"
    sort_order = str(packet.get("sort_order", sort_order) or "default")
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
        sort_order=sort_order,
        responses_json_path=responses_path,
        summary_json_path=summary_path,
        brief_json_path=brief_json_path,
        brief_markdown_path=brief_markdown_path,
        plan_json_path=plan_json_path,
        plan_markdown_path=plan_markdown_path,
        packet_json_path=packet_json_path,
        packet_markdown_path=packet_markdown_path,
        start_card_json_path=start_card_json_path,
        start_card_markdown_path=start_card_markdown_path,
        comparison_sheet_json_path=comparison_sheet_json_path,
        comparison_sheet_markdown_path=comparison_sheet_markdown_path,
        prompt_json_path=prompt_json_path,
        prompt_markdown_path=prompt_markdown_path,
        preview_run_json_path=preview_run_json_path,
        preview_run_markdown_path=preview_run_markdown_path,
        initial_detail_tab=initial_detail_tab,
        base_dir=base_dir,
    )
    window.show()
    QTimer.singleShot(0, window._fit_preview_to_window)
    app.exec()

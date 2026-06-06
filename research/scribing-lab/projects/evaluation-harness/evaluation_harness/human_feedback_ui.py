from __future__ import annotations

import json
import math
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from evaluation_harness.human_feedback_loop import (
    ALLOWED_REASON_TAGS,
    build_human_feedback_loop,
    summarize_human_review_draft_rows,
)
from evaluation_harness.human_review_response import HumanReviewResponse
from evaluation_harness.registry import ExperimentRegistry


DEFAULT_WINDOW_GEOMETRY = "1440x920"


@dataclass
class HumanFeedbackDraft:
    experiment_id: str
    decision: str = ""
    reason_tags: list[str] = field(default_factory=list)
    notes: str = ""
    reviewer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "decision": self.decision,
            "reason_tags": list(self.reason_tags),
            "notes": self.notes,
            "reviewer_id": self.reviewer_id,
        }

    @classmethod
    def from_response(cls, response: HumanReviewResponse) -> HumanFeedbackDraft:
        return cls(
            experiment_id=response.experiment_id,
            decision=response.decision,
            reason_tags=list(response.reason_tags),
            notes=response.notes,
            reviewer_id=response.reviewer_id,
        )


def load_feedback_packet(
    *,
    root: Path | None = None,
    packet_json: Path | None = None,
) -> dict[str, Any]:
    if packet_json is not None:
        data = json.loads(packet_json.read_text(encoding="utf-8"))
        return data["packet"] if "packet" in data else data
    if root is None:
        raise ValueError("root or packet_json is required")
    registry = ExperimentRegistry(root / "registry.jsonl")
    return build_human_feedback_loop(registry.load_all())["packet"]


def load_response_drafts(
    *,
    packet: dict[str, Any],
    responses_json: Path | None = None,
    reviewer_id: str = "",
) -> dict[str, HumanFeedbackDraft]:
    drafts = {
        str(item["experiment_id"]): HumanFeedbackDraft(
            experiment_id=str(item["experiment_id"]),
            reviewer_id=reviewer_id,
        )
        for item in packet.get("representatives", [])
    }
    if responses_json is None or not responses_json.exists():
        return drafts

    data = json.loads(responses_json.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "responses" in data:
            raw_responses = data["responses"]
        elif isinstance(data.get("response_summary"), dict) and "responses" in data["response_summary"]:
            raw_responses = data["response_summary"]["responses"]
        else:
            raw_responses = data
    else:
        raw_responses = data
    if not isinstance(raw_responses, list):
        raise ValueError("responses_json must contain a list or an object with responses")

    for raw in raw_responses:
        response = HumanReviewResponse.from_dict(raw)
        if response.experiment_id in drafts:
            drafts[response.experiment_id] = HumanFeedbackDraft.from_response(response)
    return drafts


def serialize_response_drafts(drafts: dict[str, HumanFeedbackDraft]) -> dict[str, Any]:
    return {
        "responses": [
            drafts[experiment_id].to_dict()
            for experiment_id in sorted(drafts)
            if drafts[experiment_id].decision
        ]
    }


def validate_response_drafts(
    packet: dict[str, Any],
    drafts: dict[str, HumanFeedbackDraft],
) -> dict[str, Any]:
    rows = [draft.to_dict() for draft in drafts.values()]
    return summarize_human_review_draft_rows(packet, rows)


class HumanFeedbackLoopApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        packet: dict[str, Any],
        drafts: dict[str, HumanFeedbackDraft],
        reviewer_id: str = "",
        responses_json_path: Path | None = None,
        summary_json_path: Path | None = None,
    ) -> None:
        self._root = root
        self._packet = packet
        self._drafts = drafts
        self._reviewer_id = reviewer_id.strip()
        self._responses_json_path = responses_json_path
        self._summary_json_path = summary_json_path
        self._current_experiment_id = self._first_experiment_id()
        self._preview_image: tk.PhotoImage | None = None

        root.title("Human Feedback Loop")
        root.geometry(DEFAULT_WINDOW_GEOMETRY)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=1)
        root.rowconfigure(2, weight=0)

        self._build_header()
        self._build_body()
        self._build_footer()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_all()

    def _build_header(self) -> None:
        header = ttk.Frame(self._root)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Reviewer").grid(row=0, column=0, sticky="w")
        self._reviewer_id_var = tk.StringVar(value=self._reviewer_id)
        reviewer_entry = ttk.Entry(header, textvariable=self._reviewer_id_var, width=24)
        reviewer_entry.grid(row=0, column=1, sticky="w", padx=(8, 16))
        reviewer_entry.bind("<KeyRelease>", lambda _event: self._sync_from_widgets())

        ttk.Button(header, text="Validate", command=self._validate_current).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(header, text="Export Responses", command=self._export_responses).grid(
            row=0, column=3, padx=4
        )
        ttk.Button(header, text="Open Summary", command=self._refresh_summary).grid(
            row=0, column=4, padx=4
        )

    def _build_body(self) -> None:
        body = ttk.Panedwindow(self._root, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)

        list_frame = ttk.Labelframe(body, text="Representatives")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self._item_listbox = tk.Listbox(list_frame, exportselection=False, height=18)
        self._item_listbox.grid(row=0, column=0, sticky="nsew")
        item_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._item_listbox.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self._item_listbox.configure(yscrollcommand=item_scroll.set)
        self._item_listbox.bind("<<ListboxSelect>>", self._on_select_item)

        for item in self._packet.get("representatives", []):
            self._item_listbox.insert(
                tk.END,
                f"{item['experiment_id']} | {item['input_text']} | seed={item['seed']}",
            )

        detail_frame = ttk.Frame(body)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=0)
        detail_frame.rowconfigure(1, weight=0)
        detail_frame.rowconfigure(2, weight=0)
        detail_frame.rowconfigure(3, weight=0)
        detail_frame.rowconfigure(4, weight=1)

        preview_frame = ttk.Labelframe(detail_frame, text="Preview")
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(0, 6))
        preview_frame.columnconfigure(0, weight=1)
        self._preview_label = ttk.Label(preview_frame, anchor="center")
        self._preview_label.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        detail_box = ttk.Labelframe(detail_frame, text="Details")
        detail_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=6)
        detail_box.columnconfigure(0, weight=1)
        self._detail_text = tk.Text(detail_box, height=8, wrap=tk.WORD)
        self._detail_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._detail_text.configure(state=tk.DISABLED)

        decision_frame = ttk.Labelframe(detail_frame, text="Decision")
        decision_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=6)
        self._decision_var = tk.StringVar(value="")
        for col, decision in enumerate(("accept", "reject", "needs-tuning")):
            ttk.Radiobutton(
                decision_frame,
                text=decision,
                value=decision,
                variable=self._decision_var,
                command=self._sync_from_widgets,
            ).grid(row=0, column=col, padx=10, pady=6, sticky="w")

        tags_frame = ttk.Labelframe(detail_frame, text="Reason Tags")
        tags_frame.grid(row=3, column=0, sticky="nsew", padx=4, pady=6)
        tags_frame.columnconfigure(0, weight=1)
        tags_frame.rowconfigure(0, weight=1)
        self._reason_listbox = tk.Listbox(tags_frame, exportselection=False, selectmode=tk.MULTIPLE, height=6)
        self._reason_listbox.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        tags_scroll = ttk.Scrollbar(tags_frame, orient=tk.VERTICAL, command=self._reason_listbox.yview)
        tags_scroll.grid(row=0, column=1, sticky="ns")
        self._reason_listbox.configure(yscrollcommand=tags_scroll.set)
        for tag in ALLOWED_REASON_TAGS:
            self._reason_listbox.insert(tk.END, tag)
        self._reason_listbox.bind("<<ListboxSelect>>", lambda _event: self._sync_from_widgets())

        notes_frame = ttk.Labelframe(detail_frame, text="Notes")
        notes_frame.grid(row=4, column=0, sticky="nsew", padx=4, pady=6)
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)
        self._notes_text = tk.Text(notes_frame, height=6, wrap=tk.WORD)
        self._notes_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._notes_text.bind("<KeyRelease>", lambda _event: self._sync_from_widgets())

        body.add(list_frame, weight=0)
        body.add(detail_frame, weight=1)

        self._summary_frame = ttk.Labelframe(self._root, text="Validation Summary")
        self._summary_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=(4, 8))
        self._summary_frame.columnconfigure(0, weight=1)
        self._summary_frame.rowconfigure(0, weight=1)
        self._summary_text = tk.Text(self._summary_frame, height=10, wrap=tk.WORD)
        self._summary_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._summary_text.configure(state=tk.DISABLED)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self._root)
        footer.grid_remove()

    def _first_experiment_id(self) -> str:
        representatives = self._packet.get("representatives", [])
        if not representatives:
            return ""
        return str(representatives[0]["experiment_id"])

    def _current_draft(self) -> HumanFeedbackDraft | None:
        if not self._current_experiment_id:
            return None
        return self._drafts[self._current_experiment_id]

    def _on_select_item(self, _event: tk.Event[Any]) -> None:
        self._sync_from_widgets()
        selection = self._item_listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        item = self._packet["representatives"][index]
        self._current_experiment_id = str(item["experiment_id"])
        self._load_current_item()

    def _load_current_item(self) -> None:
        item = self._current_item()
        draft = self._current_draft()
        if item is None or draft is None:
            return

        self._decision_var.set(draft.decision)
        self._select_reason_tags(draft.reason_tags)
        self._notes_text.delete("1.0", tk.END)
        self._notes_text.insert("1.0", draft.notes)

        self._set_detail_text(item)
        self._set_preview_image(item.get("preview", ""))

    def _current_item(self) -> dict[str, Any] | None:
        for item in self._packet.get("representatives", []):
            if str(item["experiment_id"]) == self._current_experiment_id:
                return item
        return None

    def _set_detail_text(self, item: dict[str, Any]) -> None:
        self._detail_text.configure(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        lines = [
            f"experiment_id: {item['experiment_id']}",
            f"input_text: {item['input_text']}",
            f"seed: {item['seed']}",
            f"reason: {item['reason']}",
            f"failure_tags: {item['failure_tags']}",
            f"metrics: {item['metrics']}",
        ]
        self._detail_text.insert("1.0", "\n".join(lines))
        self._detail_text.configure(state=tk.DISABLED)

    def _set_preview_image(self, path_text: str) -> None:
        self._preview_image = None
        path = Path(path_text)
        if not path_text or not path.exists():
            self._preview_label.configure(text=f"preview unavailable\n{path_text}", image="")
            return

        try:
            image = tk.PhotoImage(file=str(path))
        except tk.TclError:
            self._preview_label.configure(text=f"failed to load preview\n{path_text}", image="")
            return

        max_width, max_height = 680, 380
        width = max(image.width(), 1)
        height = max(image.height(), 1)
        scale = max(1, math.ceil(max(width / max_width, height / max_height)))
        if scale > 1:
            image = image.subsample(scale, scale)
        self._preview_image = image
        self._preview_label.configure(image=image, text="")

    def _select_reason_tags(self, reason_tags: list[str]) -> None:
        self._reason_listbox.selection_clear(0, tk.END)
        tag_set = set(reason_tags)
        for idx, tag in enumerate(ALLOWED_REASON_TAGS):
            if tag in tag_set:
                self._reason_listbox.selection_set(idx)

    def _capture_current_draft(self) -> None:
        self._apply_reviewer_id_to_all_drafts()
        draft = self._current_draft()
        if draft is None:
            return
        draft.decision = self._decision_var.get().strip()
        draft.reason_tags = [
            ALLOWED_REASON_TAGS[index]
            for index in self._reason_listbox.curselection()
        ]
        draft.notes = self._notes_text.get("1.0", tk.END).strip()
        draft.reviewer_id = self._reviewer_id_var.get().strip()

    def _apply_reviewer_id_to_all_drafts(self) -> None:
        reviewer_id = self._reviewer_id_var.get().strip()
        for draft in self._drafts.values():
            draft.reviewer_id = reviewer_id

    def _sync_from_widgets(self) -> None:
        self._capture_current_draft()
        self._refresh_summary()

    def _current_rows(self) -> list[dict[str, Any]]:
        self._capture_current_draft()
        return [draft.to_dict() for draft in self._drafts.values()]

    def _refresh_all(self) -> None:
        if self._item_listbox.size() > 0:
            self._item_listbox.selection_set(0)
        self._load_current_item()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self._capture_current_draft()
        summary = validate_response_drafts(self._packet, self._drafts)
        summary_text = self._render_summary_text(summary)
        self._summary_text.configure(state=tk.NORMAL)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert("1.0", summary_text)
        self._summary_text.configure(state=tk.DISABLED)

    def _render_summary_text(self, summary: dict[str, Any]) -> str:
        lines = [
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
                    "- save 後に validate-human-review 相当の確認を行う",
                ]
            )
        return "\n".join(lines) + "\n"

    def _validate_current(self) -> None:
        self._sync_from_widgets()
        summary = validate_response_drafts(self._packet, self._drafts)
        self._show_validation_summary(summary)
        if summary["validation_errors"]:
            messagebox.showwarning("Human Feedback Loop", "Validation errors found. See summary.")
        else:
            messagebox.showinfo("Human Feedback Loop", "Validation passed.")

    def _show_validation_summary(self, summary: dict[str, Any]) -> None:
        self._summary_text.configure(state=tk.NORMAL)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert("1.0", self._render_summary_text(summary))
        self._summary_text.configure(state=tk.DISABLED)

    def _export_responses(self) -> None:
        self._sync_from_widgets()
        summary = validate_response_drafts(self._packet, self._drafts)
        self._show_validation_summary(summary)
        if summary["validation_errors"]:
            messagebox.showwarning(
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
        messagebox.showinfo(
            "Human Feedback Loop",
            f"Saved responses to {output_path} and summary to {summary_path}",
        )

    def _on_close(self) -> None:
        try:
            self._root.destroy()
        except tk.TclError:
            pass


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
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depends on display availability
        raise RuntimeError("Tkinter UI is not available in this environment") from exc

    HumanFeedbackLoopApp(
        window,
        packet=packet,
        drafts=drafts,
        reviewer_id=reviewer_id,
        responses_json_path=responses_path,
        summary_json_path=summary_path,
    )
    window.mainloop()

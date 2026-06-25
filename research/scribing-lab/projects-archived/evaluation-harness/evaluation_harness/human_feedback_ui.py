from __future__ import annotations

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
from evaluation_harness.human_feedback_qt import launch_human_feedback_ui


__all__ = [
    "HumanFeedbackDraft",
    "_choose_font_family",
    "build_common_failure_examples",
    "build_decision_help",
    "build_review_instructions",
    "choose_font_family",
    "launch_human_feedback_ui",
    "load_feedback_packet",
    "load_response_drafts",
    "serialize_response_drafts",
    "validate_response_drafts",
]


def _choose_font_family(available_families: set[str], candidates: tuple[str, ...]) -> str:
    return choose_font_family(available_families, candidates, fallback="TkDefaultFont")

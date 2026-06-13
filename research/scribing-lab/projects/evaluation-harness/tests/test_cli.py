import json
import subprocess
from pathlib import Path
import sys

from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.cli import build_parser, run_smoke


def test_offline_review_parser_accepts_output_paths() -> None:
    args = build_parser().parse_args(
        [
            "offline-review",
            "--root",
            "runs/test",
            "--output",
            "review.md",
            "--json-output",
            "review.json",
        ]
    )

    assert args.command == "offline-review"
    assert args.root == "runs/test"
    assert args.output == "review.md"
    assert args.json_output == "review.json"


def test_human_review_packet_parser_accepts_output_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-review-packet",
            "--root",
            "runs/test",
            "--output",
            "packet.md",
            "--json-output",
            "packet.json",
        ]
    )

    assert args.command == "human-review-packet"
    assert args.root == "runs/test"
    assert args.output == "packet.md"
    assert args.json_output == "packet.json"


def test_human_feedback_loop_parser_accepts_response_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-loop",
            "--root",
            "runs/test",
            "--responses-json",
            "runs/test/human_review_responses.json",
            "--reviewer-id",
            "reviewer-1",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ]
    )

    assert args.command == "human-feedback-loop"
    assert args.root == "runs/test"
    assert args.responses_json == "runs/test/human_review_responses.json"
    assert args.reviewer_id == "reviewer-1"
    assert args.output == "loop.md"
    assert args.json_output == "loop.json"


def test_human_feedback_ui_parser_accepts_packet_or_root() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-ui",
            "--root",
            "runs/test",
            "--responses-json",
            "runs/test/human_review_responses.json",
            "--summary-json",
            "runs/test/human_review_response_summary.json",
            "--reviewer-id",
            "reviewer-1",
        ]
    )

    assert args.command == "human-feedback-ui"
    assert args.root == "runs/test"
    assert args.packet_json is None
    assert args.responses_json == "runs/test/human_review_responses.json"
    assert args.summary_json == "runs/test/human_review_response_summary.json"
    assert args.reviewer_id == "reviewer-1"
    assert args.target_count is None


def test_human_feedback_ui_parser_accepts_target_count() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-ui",
            "--root",
            "runs/test",
            "--target-count",
            "72",
        ]
    )

    assert args.command == "human-feedback-ui"
    assert args.root == "runs/test"
    assert args.target_count == 72


def test_human_feedback_ui_parser_accepts_brief_outputs() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-ui",
            "--root",
            "runs/test",
            "--brief-json",
            "runs/test/brief.json",
            "--brief-markdown",
            "runs/test/brief.md",
            "--plan-json",
            "runs/test/plan.json",
            "--plan-markdown",
            "runs/test/plan.md",
        ]
    )

    assert args.command == "human-feedback-ui"
    assert args.brief_json == "runs/test/brief.json"
    assert args.brief_markdown == "runs/test/brief.md"
    assert args.plan_json == "runs/test/plan.json"
    assert args.plan_markdown == "runs/test/plan.md"


def test_human_feedback_revision_plan_parser_accepts_brief_and_loop_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-revision-plan",
            "--brief-json",
            "runs/test/brief.json",
            "--output",
            "plan.md",
            "--json-output",
            "plan.json",
        ]
    )

    assert args.command == "human-feedback-revision-plan"
    assert args.brief_json == "runs/test/brief.json"
    assert args.output == "plan.md"
    assert args.json_output == "plan.json"


def test_human_feedback_preview_revision_plan_parser_accepts_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-preview-revision-plan",
            "--root",
            "runs/test",
            "--brief-json",
            "runs/test/brief.json",
            "--output",
            "preview-plan.md",
            "--json-output",
            "preview-plan.json",
        ]
    )

    assert args.command == "human-feedback-preview-revision-plan"
    assert args.root == "runs/test"
    assert args.brief_json == "runs/test/brief.json"
    assert args.output == "preview-plan.md"
    assert args.json_output == "preview-plan.json"


def test_human_feedback_preview_revision_run_parser_accepts_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-preview-revision-run",
            "--root",
            "runs/test",
            "--brief-json",
            "runs/test/brief.json",
            "--focus-areas",
            "layout,motion",
            "--max-items",
            "2",
            "--output",
            "preview-run.md",
            "--json-output",
            "preview-run.json",
        ]
    )

    assert args.command == "human-feedback-preview-revision-run"
    assert args.root == "runs/test"
    assert args.brief_json == "runs/test/brief.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 2
    assert args.output == "preview-run.md"
    assert args.json_output == "preview-run.json"


def test_preview_review_packet_parser_accepts_output_paths() -> None:
    args = build_parser().parse_args(
        [
            "preview-review-packet",
            "--root",
            "runs/test",
            "--output",
            "preview.md",
            "--json-output",
            "preview.json",
        ]
    )

    assert args.command == "preview-review-packet"
    assert args.root == "runs/test"
    assert args.output == "preview.md"
    assert args.json_output == "preview.json"
    assert args.target_count is None


def test_preview_review_packet_parser_accepts_target_count() -> None:
    args = build_parser().parse_args(
        [
            "preview-review-packet",
            "--root",
            "runs/test",
            "--target-count",
            "48",
            "--output",
            "preview.md",
            "--json-output",
            "preview.json",
        ]
    )

    assert args.command == "preview-review-packet"
    assert args.root == "runs/test"
    assert args.target_count == 48


def test_human_review_packet_parser_accepts_target_count() -> None:
    args = build_parser().parse_args(
        [
            "human-review-packet",
            "--root",
            "runs/test",
            "--target-count",
            "72",
            "--output",
            "review.md",
            "--json-output",
            "review.json",
        ]
    )

    assert args.command == "human-review-packet"
    assert args.root == "runs/test"
    assert args.target_count == 72
    assert args.output == "review.md"
    assert args.json_output == "review.json"


def test_human_feedback_loop_parser_accepts_target_count() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-loop",
            "--root",
            "runs/test",
            "--target-count",
            "60",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ]
    )

    assert args.command == "human-feedback-loop"
    assert args.root == "runs/test"
    assert args.target_count == 60
    assert args.output == "loop.md"
    assert args.json_output == "loop.json"


def test_human_feedback_loop_parser_accepts_brief_options() -> None:
    args = build_parser().parse_args(
        [
            "human-feedback-loop",
            "--root",
            "runs/test",
            "--brief-only",
            "--brief-output",
            "brief.md",
            "--brief-json-output",
            "brief.json",
        ]
    )

    assert args.command == "human-feedback-loop"
    assert args.brief_only is True
    assert args.brief_output == "brief.md"
    assert args.brief_json_output == "brief.json"


def test_human_abx_packet_parser_accepts_input_set_and_output_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-packet",
            "--root",
            "runs/test",
            "--input-set",
            "wide",
            "--seeds",
            "1,2",
            "--baseline-generator",
            "baseline-outline",
            "--output",
            "abx.md",
            "--json-output",
            "abx.json",
        ]
    )

    assert args.command == "human-abx-packet"
    assert args.root == "runs/test"
    assert args.input_set == "wide"
    assert args.seeds == "1,2"
    assert args.baseline_generator == "baseline-outline"
    assert args.output == "abx.md"
    assert args.json_output == "abx.json"


def test_human_abx_packet_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-packet",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout,motion",
            "--max-items",
            "12",
            "--output",
            "abx.md",
            "--json-output",
            "abx.json",
        ]
    )

    assert args.command == "human-abx-packet"
    assert args.root == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 12
    assert args.output == "abx.md"
    assert args.json_output == "abx.json"


def test_human_abx_feedback_loop_parser_accepts_packet_and_response_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-feedback-loop",
            "--packet-json",
            "runs/test/human_abx_packet.json",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--evaluator-id",
            "eval-1",
            "--max-items",
            "24",
            "--template-json-output",
            "template.json",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ]
    )

    assert args.command == "human-abx-feedback-loop"
    assert args.packet_json == "runs/test/human_abx_packet.json"
    assert args.responses_json == "runs/test/human_abx_responses.json"
    assert args.evaluator_id == "eval-1"
    assert args.max_items == 24
    assert args.template_json_output == "template.json"
    assert args.output == "loop.md"
    assert args.json_output == "loop.json"


def test_human_abx_feedback_loop_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-feedback-loop",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout,motion",
            "--max-items",
            "12",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
            "--template-json-output",
            "template.json",
        ]
    )

    assert args.command == "human-abx-feedback-loop"
    assert args.packet_json == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 12


def test_human_abx_bundle_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout",
            "--max-items",
            "18",
            "--output-dir",
            "bundle",
            "--output-prefix",
            "layout_abx",
        ]
    )

    assert args.command == "human-abx-bundle"
    assert args.root == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout"
    assert args.max_items == 18
    assert args.output_dir == "bundle"
    assert args.output_prefix == "layout_abx"


def test_human_abx_bundle_followup_parser_accepts_bundle_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx",
            "--responses-json",
            "runs/test/layout_bundle_v1/layout_abx_responses.json",
            "--workbook-json",
            "runs/test/layout_bundle_v1/layout_abx_workbook.json",
            "--output-prefix",
            "layout_abx_followup",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.root == "runs/test"
    assert args.bundle_dir == "runs/test/layout_bundle_v1"
    assert args.bundle_prefix == "layout_abx"
    assert args.workbook_json == "runs/test/layout_bundle_v1/layout_abx_workbook.json"
    assert args.responses_json == "runs/test/layout_bundle_v1/layout_abx_responses.json"
    assert args.output_prefix == "layout_abx_followup"


def test_human_abx_bundle_followup_parser_defaults_responses_path() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.workbook_json == ""
    assert args.responses_json == ""
    assert args.output_prefix == ""
    assert args.pending_only is False


def test_human_abx_bundle_followup_parser_accepts_pending_only() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx",
            "--pending-only",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.pending_only is True


def test_human_abx_bundle_followup_parser_accepts_next_bundle_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx",
            "--pending-only",
            "--next-bundle-dir",
            "runs/test/layout_bundle_v2",
            "--next-bundle-prefix",
            "layout_abx_v2",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.pending_only is True
    assert args.next_bundle_dir == "runs/test/layout_bundle_v2"
    assert args.next_bundle_prefix == "layout_abx_v2"


def test_human_abx_bundle_followup_parser_accepts_chain_next_bundle() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx_v1",
            "--pending-only",
            "--chain-next-bundle",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.pending_only is True
    assert args.chain_next_bundle is True


def test_human_abx_bundle_followup_parser_accepts_versioned_bundle_prefix() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-followup",
            "--root",
            "runs/test",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx_v1",
            "--pending-only",
            "--chain-next-bundle",
        ]
    )

    assert args.command == "human-abx-bundle-followup"
    assert args.bundle_prefix == "layout_abx_v1"


def test_human_abx_bundle_chain_status_parser_accepts_paths() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-chain-status",
            "--bundle-dir",
            "runs/test/layout_bundle_v1",
            "--bundle-prefix",
            "layout_abx",
            "--max-depth",
            "4",
            "--output",
            "status.md",
            "--json-output",
            "status.json",
        ]
    )

    assert args.command == "human-abx-bundle-chain-status"
    assert args.bundle_dir == "runs/test/layout_bundle_v1"
    assert args.bundle_prefix == "layout_abx"
    assert args.max_depth == 4
    assert args.output == "status.md"
    assert args.json_output == "status.json"


def test_human_abx_bundle_sweep_status_parser_accepts_root() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle-sweep-status",
            "--root",
            "runs/test",
            "--max-depth",
            "4",
            "--output",
            "sweep.md",
            "--json-output",
            "sweep.json",
        ]
    )

    assert args.command == "human-abx-bundle-sweep-status"
    assert args.root == "runs/test"
    assert args.max_depth == 4
    assert args.output == "sweep.md"
    assert args.json_output == "sweep.json"


def test_abx_workbook_parser_accepts_packet_and_response_paths() -> None:
    args = build_parser().parse_args(
        [
            "abx-workbook",
            "--packet-json",
            "runs/test/human_abx_packet.json",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--evaluator-id",
            "eval-1",
            "--max-items",
            "24",
            "--responses-output",
            "responses.json",
            "--output",
            "workbook.md",
            "--json-output",
            "workbook.json",
        ]
    )

    assert args.command == "abx-workbook"
    assert args.packet_json == "runs/test/human_abx_packet.json"
    assert args.responses_json == "runs/test/human_abx_responses.json"
    assert args.evaluator_id == "eval-1"
    assert args.max_items == 24
    assert args.responses_output == "responses.json"
    assert args.output == "workbook.md"
    assert args.json_output == "workbook.json"


def test_abx_workbook_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "abx-workbook",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout,motion",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--evaluator-id",
            "eval-1",
            "--max-items",
            "24",
            "--responses-output",
            "responses.json",
            "--output",
            "workbook.md",
            "--json-output",
            "workbook.json",
        ]
    )

    assert args.command == "abx-workbook"
    assert args.packet_json == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 24


def test_human_abx_bundle_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "human-abx-bundle",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout",
            "--output-dir",
            "bundle",
            "--output-prefix",
            "layout_abx",
        ]
    )

    assert args.command == "human-abx-bundle"
    assert args.root == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout"
    assert args.output_dir == "bundle"
    assert args.output_prefix == "layout_abx"


def test_validate_abx_responses_parser_accepts_packet_and_response_paths() -> None:
    args = build_parser().parse_args(
        [
            "validate-abx-responses",
            "--packet-json",
            "runs/test/human_abx_packet.json",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--output",
            "summary.md",
            "--json-output",
            "summary.json",
        ]
    )

    assert args.command == "validate-abx-responses"
    assert args.packet_json == "runs/test/human_abx_packet.json"
    assert args.responses_json == "runs/test/human_abx_responses.json"
    assert args.output == "summary.md"
    assert args.json_output == "summary.json"


def test_abx_revision_plan_parser_accepts_feedback_loop_path() -> None:
    args = build_parser().parse_args(
        [
            "abx-revision-plan",
            "--feedback-loop-json",
            "runs/test/human_abx_feedback_loop.json",
            "--output",
            "revision.md",
            "--json-output",
            "revision.json",
        ]
    )

    assert args.command == "abx-revision-plan"
    assert args.feedback_loop_json == "runs/test/human_abx_feedback_loop.json"
    assert args.output == "revision.md"
    assert args.json_output == "revision.json"


def test_abx_revision_plan_parser_accepts_packet_and_responses_paths() -> None:
    args = build_parser().parse_args(
        [
            "abx-revision-plan",
            "--packet-json",
            "runs/test/human_abx_packet.json",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--max-items",
            "18",
            "--evaluator-id",
            "eval-1",
            "--output",
            "revision.md",
            "--json-output",
            "revision.json",
        ]
    )

    assert args.command == "abx-revision-plan"
    assert args.packet_json == "runs/test/human_abx_packet.json"
    assert args.responses_json == "runs/test/human_abx_responses.json"
    assert args.max_items == 18
    assert args.evaluator_id == "eval-1"
    assert args.output == "revision.md"
    assert args.json_output == "revision.json"


def test_abx_revision_plan_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "abx-revision-plan",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout,motion",
            "--max-items",
            "18",
            "--evaluator-id",
            "eval-1",
            "--output",
            "revision.md",
            "--json-output",
            "revision.json",
        ]
    )

    assert args.command == "abx-revision-plan"
    assert args.feedback_loop_json == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 18


def test_abx_revision_run_parser_accepts_packet_and_responses_paths() -> None:
    args = build_parser().parse_args(
        [
            "abx-revision-run",
            "--root",
            "runs/test",
            "--packet-json",
            "runs/test/human_abx_packet.json",
            "--responses-json",
            "runs/test/human_abx_responses.json",
            "--max-items",
            "18",
            "--evaluator-id",
            "eval-1",
            "--output",
            "run.md",
            "--json-output",
            "run.json",
        ]
    )

    assert args.command == "abx-revision-run"
    assert args.root == "runs/test"
    assert args.packet_json == "runs/test/human_abx_packet.json"
    assert args.responses_json == "runs/test/human_abx_responses.json"
    assert args.max_items == 18
    assert args.evaluator_id == "eval-1"
    assert args.output == "run.md"
    assert args.json_output == "run.json"


def test_abx_revision_run_parser_accepts_recommendation_json() -> None:
    args = build_parser().parse_args(
        [
            "abx-revision-run",
            "--root",
            "runs/test",
            "--recommendation-json",
            "runs/test/wide_profile_recommendation.json",
            "--focus-areas",
            "layout,motion",
            "--max-items",
            "18",
            "--evaluator-id",
            "eval-1",
            "--output",
            "run.md",
            "--json-output",
            "run.json",
        ]
    )

    assert args.command == "abx-revision-run"
    assert args.root == "runs/test"
    assert args.packet_json == ""
    assert args.recommendation_json == "runs/test/wide_profile_recommendation.json"
    assert args.focus_areas == "layout,motion"
    assert args.max_items == 18


def test_validate_human_review_parser_accepts_response_paths() -> None:
    args = build_parser().parse_args(
        [
            "validate-human-review",
            "--packet-json",
            "runs/test/human_review_packet.json",
            "--responses-json",
            "runs/test/human_review_responses.json",
            "--output",
            "summary.md",
            "--json-output",
            "summary.json",
        ]
    )

    assert args.command == "validate-human-review"
    assert args.packet_json == "runs/test/human_review_packet.json"
    assert args.responses_json == "runs/test/human_review_responses.json"
    assert args.output == "summary.md"
    assert args.json_output == "summary.json"


def test_plot_ready_packet_parser_accepts_summary_paths() -> None:
    args = build_parser().parse_args(
        [
            "plot-ready-packet",
            "--root",
            "runs/test",
            "--human-summary-json",
            "runs/test/human_review_response_summary.json",
            "--output",
            "plot_ready.md",
            "--json-output",
            "plot_ready.json",
        ]
    )

    assert args.command == "plot-ready-packet"
    assert args.root == "runs/test"
    assert args.human_summary_json == "runs/test/human_review_response_summary.json"
    assert args.output == "plot_ready.md"
    assert args.json_output == "plot_ready.json"


def test_compare_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "compare-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--input-set",
            "wide",
            "--output",
            "fixed.md",
            "--json-output",
            "fixed.json",
        ]
    )

    assert args.command == "compare-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.input_set == "wide"
    assert args.output == "fixed.md"
    assert args.json_output == "fixed.json"


def test_baseline_outline_batch_parser_accepts_input_set() -> None:
    args = build_parser().parse_args(
        [
            "baseline-outline-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--input-set",
            "wide",
        ]
    )

    assert args.command == "baseline-outline-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.input_set == "wide"


def test_baseline_outline_batch_parser_accepts_experiment_prefix() -> None:
    args = build_parser().parse_args(
        [
            "baseline-outline-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--experiment-prefix",
            "exp-baseline-wide",
        ]
    )

    assert args.command == "baseline-outline-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.experiment_prefix == "exp-baseline-wide"


def test_structure_uniform_batch_parser_accepts_wide_input_set() -> None:
    args = build_parser().parse_args(
        [
            "structure-uniform-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--input-set",
            "wide",
        ]
    )

    assert args.command == "structure-uniform-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.input_set == "wide"


def test_structure_uniform_batch_parser_accepts_experiment_prefix() -> None:
    args = build_parser().parse_args(
        [
            "structure-uniform-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--experiment-prefix",
            "exp-structure-wide",
        ]
    )

    assert args.command == "structure-uniform-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.experiment_prefix == "exp-structure-wide"


def test_structure_motion_batch_parser_accepts_wide_input_set() -> None:
    args = build_parser().parse_args(
        [
            "structure-motion-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--input-set",
            "wide",
        ]
    )

    assert args.command == "structure-motion-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.input_set == "wide"


def test_structure_motion_batch_parser_accepts_experiment_prefix() -> None:
    args = build_parser().parse_args(
        [
            "structure-motion-batch",
            "--root",
            "runs/test",
            "--seeds",
            "1,2",
            "--experiment-prefix",
            "exp-motion-fast",
        ]
    )

    assert args.command == "structure-motion-batch"
    assert args.root == "runs/test"
    assert args.seeds == "1,2"
    assert args.experiment_prefix == "exp-motion-fast"


def test_compare_preview_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "compare-preview-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--output",
            "preview.md",
            "--json-output",
            "preview.json",
        ]
    )

    assert args.command == "compare-preview-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.output == "preview.md"
    assert args.json_output == "preview.json"


def test_recommend_preview_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "recommend-preview-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--output",
            "recommend.md",
            "--json-output",
            "recommend.json",
        ]
    )

    assert args.command == "recommend-preview-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.output == "recommend.md"
    assert args.json_output == "recommend.json"


def test_propose_preview_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "propose-preview-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--output",
            "propose.md",
            "--json-output",
            "propose.json",
        ]
    )

    assert args.command == "propose-preview-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.output == "propose.md"
    assert args.json_output == "propose.json"


def test_preview_iteration_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "preview-iteration-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--output",
            "iteration.md",
            "--json-output",
            "iteration.json",
        ]
    )

    assert args.command == "preview-iteration-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.output == "iteration.md"
    assert args.json_output == "iteration.json"


def test_apply_preview_revision_fixed_inputs_parser_accepts_seeds() -> None:
    args = build_parser().parse_args(
        [
            "apply-preview-revision-fixed-inputs",
            "--root",
            "runs/test",
            "--baseline-generator",
            "baseline-outline",
            "--seeds",
            "1,2",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ]
    )

    assert args.command == "apply-preview-revision-fixed-inputs"
    assert args.root == "runs/test"
    assert args.baseline_generator == "baseline-outline"
    assert args.seeds == "1,2"
    assert args.output == "loop.md"
    assert args.json_output == "loop.json"


def test_apply_preview_revision_fixed_inputs_parser_accepts_revision_plan_json() -> None:
    args = build_parser().parse_args(
        [
            "apply-preview-revision-fixed-inputs",
            "--root",
            "runs/test",
            "--revision-plan-json",
            "runs/test/plan.json",
        ]
    )

    assert args.command == "apply-preview-revision-fixed-inputs"
    assert args.root == "runs/test"
    assert args.revision_plan_json == "runs/test/plan.json"


def test_summarize_preview_revision_loops_parser_accepts_packets() -> None:
    args = build_parser().parse_args(
        [
            "summarize-preview-revision-loops",
            "--packet-json",
            "runs/test/loop-a.json",
            "runs/test/loop-b.json",
            "--output",
            "summary.md",
            "--json-output",
            "summary.json",
        ]
    )

    assert args.command == "summarize-preview-revision-loops"
    assert args.packet_json == ["runs/test/loop-a.json", "runs/test/loop-b.json"]
    assert args.output == "summary.md"
    assert args.json_output == "summary.json"


def test_propose_stable_writer_profiles_parser_accepts_summary_path() -> None:
    args = build_parser().parse_args(
        [
            "propose-stable-writer-profiles",
            "--summary-json",
            "runs/test/summary.json",
            "--base-profile-id",
            "baseline-neat",
            "--output",
            "stable.md",
            "--json-output",
            "stable.json",
        ]
    )

    assert args.command == "propose-stable-writer-profiles"
    assert args.summary_json == "runs/test/summary.json"
    assert args.base_profile_id == "baseline-neat"
    assert args.output == "stable.md"
    assert args.json_output == "stable.json"


def test_evaluate_stable_writer_profiles_parser_accepts_summary_and_root() -> None:
    args = build_parser().parse_args(
        [
            "evaluate-stable-writer-profiles",
            "--summary-json",
            "runs/test/summary.json",
            "--root",
            "runs/test",
            "--base-profile-id",
            "baseline-neat",
            "--seeds",
            "1,2",
            "--output",
            "stable_eval.md",
            "--json-output",
            "stable_eval.json",
        ]
    )

    assert args.command == "evaluate-stable-writer-profiles"
    assert args.summary_json == "runs/test/summary.json"
    assert args.root == "runs/test"
    assert args.base_profile_id == "baseline-neat"
    assert args.seeds == "1,2"
    assert args.output == "stable_eval.md"
    assert args.json_output == "stable_eval.json"


def test_evaluate_data_driven_writer_prior_parser_accepts_samples_and_root() -> None:
    args = build_parser().parse_args(
        [
            "evaluate-data-driven-writer-prior",
            "--samples-jsonl",
            "runs/test/samples.jsonl",
            "--root",
            "runs/test",
            "--base-profile-id",
            "baseline-neat",
            "--seeds",
            "1,2",
            "--output",
            "prior_eval.md",
            "--json-output",
            "prior_eval.json",
        ]
    )

    assert args.command == "evaluate-data-driven-writer-prior"
    assert args.samples_jsonl == "runs/test/samples.jsonl"
    assert args.root == "runs/test"
    assert args.base_profile_id == "baseline-neat"
    assert args.seeds == "1,2"
    assert args.output == "prior_eval.md"
    assert args.json_output == "prior_eval.json"


def test_structure_motion_parser_accepts_shape_variation() -> None:
    args = build_parser().parse_args(
        [
            "structure-motion-batch",
            "--root",
            "runs/test",
            "--shape-variation",
            "0.08",
            "--layout-variation",
            "0.12",
            "--input-set",
            "extended",
        ]
    )

    assert args.command == "structure-motion-batch"
    assert args.shape_variation == 0.08
    assert args.layout_variation == 0.12
    assert args.input_set == "extended"


def test_structure_motion_parser_accepts_evaluation_input_set() -> None:
    args = build_parser().parse_args(
        [
            "structure-motion-batch",
            "--root",
            "runs/test",
            "--input-set",
            "evaluation",
        ]
    )

    assert args.command == "structure-motion-batch"
    assert args.input_set == "evaluation"


def test_structure_motion_parser_accepts_review_input_set() -> None:
    args = build_parser().parse_args(
        [
            "structure-motion-batch",
            "--root",
            "runs/test",
            "--input-set",
            "review",
        ]
    )

    assert args.command == "structure-motion-batch"
    assert args.input_set == "review"


def test_run_smoke_registers_a_complete_record(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    run_smoke(root, "exp-smoke", "永")

    registry_path = root / "registry.jsonl"
    assert registry_path.exists()
    text = registry_path.read_text(encoding="utf-8")
    assert '"report"' in text
    assert '"next_action"' in text


def test_compare_fixed_inputs_command_writes_reports(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    for input_text in DEFAULT_EVALUATION_INPUTS:
        for seed in (1, 2):
            baseline_id = f"exp-baseline-{input_text}-{seed}"
            candidate_id = f"exp-candidate-{input_text}-{seed}"
            registry.append(
                _record(
                    experiment_id=baseline_id,
                    input_text=input_text,
                    seed=seed,
                    generator="baseline-outline",
                )
            )
            registry.append(
                _record(
                    experiment_id=candidate_id,
                    input_text=input_text,
                    seed=seed,
                    generator="structure-uniform",
                    metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
                    failure_tags=["terminal-too-uniform"],
                )
            )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "compare-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1,2",
            "--output",
            "fixed.md",
            "--json-output",
            "fixed.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "fixed.md").read_text(encoding="utf-8")
    json_text = (root / "fixed.json").read_text(encoding="utf-8")

    assert "Fixed Input Comparison Report" in markdown
    assert "coverage_ratio" in markdown
    assert '"coverage_ratio": 1.0' in json_text


def test_compare_preview_fixed_inputs_command_writes_reports(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    for input_text in DEFAULT_EVALUATION_INPUTS:
        for seed in (1, 2):
            baseline_id = f"exp-baseline-{input_text}-{seed}"
            candidate_id = f"exp-candidate-{input_text}-{seed}"
            baseline_preview = root / f"{baseline_id}.png"
            candidate_preview = root / f"{candidate_id}.png"
            baseline_preview.parent.mkdir(parents=True, exist_ok=True)
            baseline_preview.write_bytes(b"baseline")
            candidate_preview.write_bytes(b"candidate")
            registry.append(
                _record(
                    experiment_id=baseline_id,
                    input_text=input_text,
                    seed=seed,
                    generator="baseline-outline",
                    artifacts={"preview": str(baseline_preview)},
                )
            )
            registry.append(
                _record(
                    experiment_id=candidate_id,
                    input_text=input_text,
                    seed=seed,
                    generator="structure-motion",
                    metrics={"duration_ms": 900, "draw_speed_cv": 0.2},
                    failure_tags=["terminal-too-uniform"],
                    artifacts={"preview": str(candidate_preview)},
                )
            )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "compare-preview-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1,2",
            "--output",
            "preview.md",
            "--json-output",
            "preview.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "preview.md").read_text(encoding="utf-8")
    json_text = (root / "preview.json").read_text(encoding="utf-8")

    assert "Preview Comparison Report" in markdown
    assert "preview_hash_changed_count" in markdown
    assert f'"preview_hash_changed_count": {len(DEFAULT_EVALUATION_INPUTS) * 2}' in json_text


def test_recommend_preview_fixed_inputs_command_writes_reports(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    good_preview = root / "good.png"
    bad_preview = root / "bad.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    good_preview.write_bytes(b"good")
    bad_preview.write_bytes(b"bad")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-good",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "velocity_peak_count": 3,
                "draw_speed_cv": 0.2,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(good_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-bad",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={"velocity_peak_count": 0, "draw_speed_cv": 0.01},
            artifacts={"preview": str(bad_preview)},
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "recommend-preview-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1",
            "--output",
            "recommend.md",
            "--json-output",
            "recommend.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "recommend.md").read_text(encoding="utf-8")
    json_text = (root / "recommend.json").read_text(encoding="utf-8")

    assert "Preview Recommendation Report" in markdown
    assert "selected_candidate_count" in markdown
    assert '"selected_candidate_count": 1' in json_text


def test_propose_preview_fixed_inputs_command_writes_reports(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "propose-preview-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1",
            "--output",
            "propose.md",
            "--json-output",
            "propose.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "propose.md").read_text(encoding="utf-8")
    json_text = (root / "propose.json").read_text(encoding="utf-8")

    assert "Preview Revision Plan" in markdown
    assert "proposed_changes" in markdown
    assert '"focus_area": "motion"' in json_text


def test_preview_iteration_fixed_inputs_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "preview-iteration-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1",
            "--output",
            "iteration.md",
            "--json-output",
            "iteration.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "iteration.md").read_text(encoding="utf-8")
    json_text = (root / "iteration.json").read_text(encoding="utf-8")

    assert "Preview Iteration Report" in markdown
    assert "iteration_status" in markdown
    assert '"iteration_status": "partial"' in json_text


def test_apply_preview_revision_fixed_inputs_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "apply-preview-revision-fixed-inputs",
            "--root",
            str(root),
            "--seeds",
            "1",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "loop.md").read_text(encoding="utf-8")
    json_text = (root / "loop.json").read_text(encoding="utf-8")

    assert "Preview Revision Loop" in markdown
    assert "rerun_count" in markdown
    assert '"rerun_count": 1' in json_text


def test_apply_preview_revision_fixed_inputs_command_accepts_revision_plan_json(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )
    revision_plan = root / "human_review_preview_revision_plan.json"
    revision_plan.parent.mkdir(parents=True, exist_ok=True)
    revision_plan.write_text(
        json.dumps(
            {
                "plan_status": "ready",
                "human_focus_area": "layout",
                "human_next_experiment_hint": "同じ input / seed で layout spacing と baseline drift を調整する",
                "preview_revision_plans": [
                    {
                        "input_text": "永",
                        "seed": 1,
                        "status": "selected",
                        "focus_area": "layout",
                        "candidate_experiment_id": "exp-candidate",
                        "candidate_profile_id": "fast-casual",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "next_experiment_hint": "同じ input / seed で layout spacing と baseline drift を調整する",
                        "proposed_changes": [
                            {
                                "target": "layout",
                                "parameter": "spacing_mean_mm",
                                "direction": "decrease",
                                "amount_hint": 0.15,
                                "reason": "字間を詰めて広がりすぎを抑える",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "apply-preview-revision-fixed-inputs",
            "--root",
            str(root),
            "--revision-plan-json",
            str(revision_plan),
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "loop.md").read_text(encoding="utf-8")
    json_text = (root / "loop.json").read_text(encoding="utf-8")

    assert "Preview Revision Loop" in markdown
    assert "rerun_count" in markdown
    assert '"rerun_count": 1' in json_text


def test_summarize_preview_revision_loops_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    packet_a = root / "loop-a.json"
    packet_b = root / "loop-b.json"
    packet_a.write_text(
        """
{
  "baseline_generator": "baseline-outline",
  "expected_input_texts": ["永"],
  "expected_seeds": [1],
  "rerun_count": 1,
  "coverage_delta": 0.0,
  "selected_candidate_delta": 0,
  "design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
  ],
  "comparison_summary": {
    "comparison_count": 1,
    "metric_names": ["draw_speed_cv"],
    "resolved_failure_tags": ["too-uniform"],
    "new_failure_tags": []
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    packet_b.write_text(
        """
{
  "baseline_generator": "baseline-outline",
  "expected_input_texts": ["永"],
  "expected_seeds": [2],
  "rerun_count": 2,
  "coverage_delta": 0.1,
  "selected_candidate_delta": 1,
  "design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
    "layout: 長文が機械的なら baseline_drift_mm を増やす"
  ],
  "comparison_summary": {
    "comparison_count": 2,
    "metric_names": ["draw_speed_cv", "baseline_drift_mm"],
    "resolved_failure_tags": ["too-uniform", "line-too-mechanical"],
    "new_failure_tags": []
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "summarize-preview-revision-loops",
            "--packet-json",
            str(packet_a),
            str(packet_b),
            "--output",
            "summary.md",
            "--json-output",
            "summary.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "summary.md").read_text(encoding="utf-8")
    json_text = (root / "summary.json").read_text(encoding="utf-8")

    assert "Preview Revision Loop Summary" in markdown
    assert "stable_design_principles" in markdown
    assert '"packet_count": 2' in json_text


def test_propose_stable_writer_profiles_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "summary.json"
    summary_path.write_text(
        """
{
  "packet_count": 2,
  "stable_design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
  ],
  "recurring_design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
    "layout: 長文が機械的なら baseline_drift_mm を増やす"
  ],
  "design_principle_counts": {
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる": 2,
    "layout: 長文が機械的なら baseline_drift_mm を増やす": 2
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "propose-stable-writer-profiles",
            "--summary-json",
            str(summary_path),
            "--base-profile-id",
            "baseline-neat",
            "--output",
            "stable.md",
            "--json-output",
            "stable.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "stable.md").read_text(encoding="utf-8")
    json_text = (root / "stable.json").read_text(encoding="utf-8")

    assert "Stable Writer Profile Candidates" in markdown
    assert "### stable" in markdown
    assert "### recurring" in markdown
    assert '"candidate_count": 2' not in json_text
    assert '"base_profile_id": "baseline-neat"' in json_text


def test_evaluate_stable_writer_profiles_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "summary.json"
    summary_path.write_text(
        """
{
  "packet_count": 2,
  "stable_design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる"
  ],
  "recurring_design_principles": [
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる",
    "layout: 長文が機械的なら baseline_drift_mm を増やす"
  ],
  "design_principle_counts": {
    "motion: 等速感が強いときは timing_jitter_cv を先に上げる": 2,
    "layout: 長文が機械的なら baseline_drift_mm を増やす": 2
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "evaluation_harness.cli.evaluate_stable_writer_profile_candidates",
        lambda *_args, **_kwargs: {
            "base_profile_id": "baseline-neat",
            "expected_input_texts": ["永"],
            "expected_seeds": [1, 2],
            "baseline_record_count": 2,
            "candidate_count": 2,
            "selected_profile_ids": ["baseline-neat-stable-1234"],
            "selected_profile_count": 1,
            "candidate_evaluations": [
                {
                    "candidate_type": "stable",
                    "profile": {"profile_id": "baseline-neat-stable-1234"},
                    "selected": True,
                    "support_count": 2,
                    "support_ratio": 1.0,
                    "selection_reason": "selected",
                    "applied_changes": [],
                    "evaluation": {"comparison_count": 2},
                }
            ],
            "selected_candidates": [
                {"candidate_type": "stable", "profile": {"profile_id": "baseline-neat-stable-1234"}}
            ],
            "selection_summary": {
                "candidate_count": 2,
                "selected_candidate_count": 1,
                "rejected_candidate_count": 1,
                "selected_coverage_ratio": 0.5,
                "selection_status": "ready",
                "selected_candidate_types": ["stable"],
                "selected_candidate_profile_ids": ["baseline-neat-stable-1234"],
            },
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "evaluate-stable-writer-profiles",
            "--summary-json",
            str(summary_path),
            "--root",
            str(root),
            "--base-profile-id",
            "baseline-neat",
            "--seeds",
            "1,2",
            "--output",
            "stable_eval.md",
            "--json-output",
            "stable_eval.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "stable_eval.md").read_text(encoding="utf-8")
    json_text = (root / "stable_eval.json").read_text(encoding="utf-8")

    assert "Stable Writer Profile Evaluation" in markdown
    assert "selected_profile_ids" in markdown
    assert '"selected_profile_count": 1' in json_text


def test_evaluate_data_driven_writer_prior_command_writes_reports(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    samples_path = root / "samples.jsonl"
    samples_path.write_text(
        """
{"sample_id":"sample-1","writer_id":"writer-a","char_or_text":"永","x_mm":0.0,"y_mm":0.0,"t_ms":0,"pen_state":1,"pressure_optional":1.0,"source":"stylus","license_scope":"research-only"}
{"sample_id":"sample-1","writer_id":"writer-a","char_or_text":"永","x_mm":1.0,"y_mm":1.0,"t_ms":10,"pen_state":1,"pressure_optional":1.0,"source":"stylus","license_scope":"research-only"}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "evaluation_harness.cli.evaluate_data_driven_writer_prior_fixed_input_set",
        lambda *_args, **_kwargs: {
            "base_profile_id": "baseline-neat",
            "samples_jsonl": str(samples_path),
            "expected_input_texts": ["永"],
            "expected_seeds": [1],
            "selected": True,
            "selected_profile_id": "baseline-neat-data-prior-1234",
            "selection_reason": "selected",
            "estimate": {
                "source": "data-driven",
                "summary": {"sample_count": 1, "writer_count": 1},
            },
            "comparison": {
                "comparison_count": 1,
                "resolved_failure_tag_count": 1,
                "new_failure_tag_count": 0,
                "safety_violation_count": 0,
                "metric_delta_means": {"draw_speed_cv": 0.1},
            },
            "evaluation_summary": {
                "selection_status": "selected",
                "candidate_count": 1,
                "selected_candidate_count": 1,
                "resolved_failure_tag_count": 1,
                "new_failure_tag_count": 0,
                "safety_violation_count": 0,
                "metric_delta_means": {"draw_speed_cv": 0.1},
            },
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "evaluate-data-driven-writer-prior",
            "--samples-jsonl",
            str(samples_path),
            "--root",
            str(root),
            "--base-profile-id",
            "baseline-neat",
            "--seeds",
            "1",
            "--output",
            "prior_eval.md",
            "--json-output",
            "prior_eval.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "prior_eval.md").read_text(encoding="utf-8")
    json_text = (root / "prior_eval.json").read_text(encoding="utf-8")

    assert "Data-driven Writer Prior Evaluation" in markdown
    assert "selected_profile_id" in markdown
    assert '"selected": true' in json_text


def test_preview_review_packet_command_writes_reports(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-a",
            input_text="永",
            seed=1,
            generator="structure-motion",
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "preview-review-packet",
            "--root",
            str(root),
            "--output",
            "preview.md",
            "--json-output",
            "preview.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "preview.md").read_text(encoding="utf-8")
    json_text = (root / "preview.json").read_text(encoding="utf-8")

    assert "Human Review Packet" in markdown
    assert "representative_count" in markdown
    assert '"representative_count": 1' in json_text


def test_human_review_packet_command_supports_large_target_count(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    for index in range(40):
        registry.append(
            _record(
                experiment_id=f"exp-{index:02d}",
                input_text="永",
                seed=index,
                generator="structure-motion",
                metrics={
                    "draw_speed_cv": 0.2 + index * 0.01,
                    "mean_abs_jerk_mm_s3": 1000.0 + index * 10.0,
                    "baseline_drift_mm": 0.2,
                    "shape_variation_mm": 0.64,
                    "layout_variation_mm": 0.96,
                    "gcode_safety_ok": 1,
                    "gcode_safety_violation_count": 0,
                },
            )
        )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-review-packet",
            "--root",
            str(root),
            "--target-count",
            "32",
            "--output",
            "review.md",
            "--json-output",
            "review.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "review.md").read_text(encoding="utf-8")
    json_text = (root / "review.json").read_text(encoding="utf-8")

    assert "Human Review Packet" in markdown
    assert "representative_count: `32`" in markdown
    assert '"representative_count": 32' in json_text


def test_human_feedback_loop_command_supports_large_target_count(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    for index in range(40):
        registry.append(
            _record(
                experiment_id=f"exp-{index:02d}",
                input_text="永",
                seed=index,
                generator="structure-motion",
                metrics={
                    "draw_speed_cv": 0.2 + index * 0.01,
                    "mean_abs_jerk_mm_s3": 1000.0 + index * 10.0,
                    "baseline_drift_mm": 0.2,
                    "shape_variation_mm": 0.64,
                    "layout_variation_mm": 0.96,
                    "gcode_safety_ok": 1,
                    "gcode_safety_violation_count": 0,
                },
            )
        )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-loop",
            "--root",
            str(root),
            "--target-count",
            "32",
            "--output",
            "loop.md",
            "--json-output",
            "loop.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "loop.md").read_text(encoding="utf-8")
    json_text = (root / "loop.json").read_text(encoding="utf-8")

    assert "Human Feedback Loop" in markdown
    assert "representative_count: `32`" in markdown
    assert '"representative_count": 32' in json_text


def test_human_feedback_loop_command_writes_revision_brief(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-a",
            input_text="永",
            seed=1,
            generator="structure-motion",
        )
    )
    responses_path = root / "human_review_responses.json"
    responses_path.parent.mkdir(parents=True, exist_ok=True)
    responses_path.write_text(
        json.dumps(
            {
                "responses": [
                    {
                        "experiment_id": "exp-a",
                        "decision": "needs-tuning",
                        "reason_tags": ["spacing-too-wide"],
                        "notes": "字間が広い",
                        "reviewer_id": "reviewer-1",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-loop",
            "--root",
            str(root),
            "--responses-json",
            str(responses_path),
            "--brief-only",
        ],
    )

    from evaluation_harness.cli import main

    main()

    brief_md = (root / "human_review_revision_brief.md").read_text(encoding="utf-8")
    brief_json = (root / "human_review_revision_brief.json").read_text(encoding="utf-8")
    plan_md = (root / "human_review_revision_plan.md").read_text(encoding="utf-8")
    plan_json = (root / "human_review_revision_plan.json").read_text(encoding="utf-8")

    assert "Human Review Revision Brief" in brief_md
    assert "字間が広い" in brief_md
    assert '"brief_status": "ready"' in brief_json
    assert "Human Review Revision Plan" in plan_md
    assert '"plan_status": "ready"' in plan_json


def test_human_feedback_revision_plan_command_writes_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "brief_status": "ready",
                "note_count": 1,
                "reason_tag_counts": {"spacing-too-wide": 1},
                "primary_notes": ["字間が広い"],
                "selected_note_examples": [
                    {
                        "experiment_id": "exp-a",
                        "decision": "needs-tuning",
                        "reason_tags": ["spacing-too-wide"],
                        "notes": "字間が広い",
                        "reviewer_id": "reviewer-1",
                    }
                ],
                "top_reason_tags": ["spacing-too-wide"],
                "focus_lines": ["notes の指摘をそのまま次回の修正に反映する"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-revision-plan",
            "--brief-json",
            str(brief_path),
            "--output",
            "plan.md",
            "--json-output",
            "plan.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    plan_md = (tmp_path / "plan.md").read_text(encoding="utf-8")
    plan_json = (tmp_path / "plan.json").read_text(encoding="utf-8")

    assert "Human Review Revision Plan" in plan_md
    assert "字間が広い" in plan_md
    assert '"plan_status": "ready"' in plan_json


def test_human_feedback_preview_revision_plan_command_writes_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            profile_id="fast-casual",
            metrics={
                "draw_speed_cv": 0.2,
                "mean_abs_jerk_mm_s3": 1000.0,
                "baseline_drift_mm": 0.3,
                "shape_variation_mm": 0.64,
                "layout_variation_mm": 0.96,
                "gcode_safety_ok": 1,
                "gcode_safety_violation_count": 0,
            },
        )
    )
    brief_path = root / "brief.json"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(
        json.dumps(
            {
                "brief_status": "ready",
                "note_count": 1,
                "reason_tag_counts": {"spacing-too-wide": 1},
                "primary_notes": ["字間が広い"],
                "selected_note_examples": [
                    {
                        "experiment_id": "exp-a",
                        "decision": "needs-tuning",
                        "reason_tags": ["spacing-too-wide"],
                        "notes": "字間が広い",
                        "reviewer_id": "reviewer-1",
                    }
                ],
                "top_reason_tags": ["spacing-too-wide"],
                "focus_lines": ["notes の指摘をそのまま次回の修正に反映する"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-preview-revision-plan",
            "--root",
            str(root),
            "--brief-json",
            str(brief_path),
            "--output",
            "preview-plan.md",
            "--json-output",
            "preview-plan.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    plan_md = (root / "preview-plan.md").read_text(encoding="utf-8")
    plan_json = (root / "preview-plan.json").read_text(encoding="utf-8")

    assert "Human Review Preview Revision Plan" in plan_md
    assert "Human Review Revision Brief" in plan_md
    assert "Human Review Revision Plan" in plan_md
    assert "Preview Revision Proposal" in plan_md
    assert '"human_focus_area": "layout"' in plan_json


def test_human_feedback_preview_revision_run_command_writes_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            profile_id="fast-casual",
            failure_tags=["spacing-too-wide"],
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )
    brief_path = root / "brief.json"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(
        json.dumps(
            {
                "brief_status": "ready",
                "note_count": 1,
                "reason_tag_counts": {"spacing-too-wide": 1},
                "primary_notes": ["字間が広い"],
                "selected_note_examples": [
                    {
                        "experiment_id": "exp-a",
                        "decision": "needs-tuning",
                        "reason_tags": ["spacing-too-wide"],
                        "notes": "字間が広い",
                        "reviewer_id": "reviewer-1",
                    }
                ],
                "top_reason_tags": ["spacing-too-wide"],
                "focus_lines": ["notes の指摘をそのまま次回の修正に反映する"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-preview-revision-run",
            "--root",
            str(root),
            "--brief-json",
            str(brief_path),
            "--output",
            "preview-run.md",
            "--json-output",
            "preview-run.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    markdown = (root / "preview-run.md").read_text(encoding="utf-8")
    json_text = (root / "preview-run.json").read_text(encoding="utf-8")

    assert "Preview Revision Loop" in markdown
    assert "human_revision_plan" in json_text
    assert "preview_revision_run" in json_text


def test_human_feedback_preview_revision_run_command_honors_focus_area_and_max_items(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "runs"
    registry = ExperimentRegistry(root / "registry.jsonl")
    baseline_preview = root / "baseline.png"
    candidate_preview = root / "candidate.png"
    baseline_preview.parent.mkdir(parents=True, exist_ok=True)
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")
    registry.append(
        _record(
            experiment_id="exp-baseline",
            input_text="永",
            seed=1,
            generator="baseline-outline",
            artifacts={"preview": str(baseline_preview)},
        )
    )
    registry.append(
        _record(
            experiment_id="exp-candidate",
            input_text="永",
            seed=1,
            generator="structure-motion",
            profile_id="fast-casual",
            failure_tags=["spacing-too-wide"],
            metrics={
                "point_count": 10,
                "velocity_peak_count": 0,
                "draw_speed_cv": 0.01,
                "shape_variation_mm": 0.6,
                "layout_variation_mm": 0.6,
            },
            artifacts={"preview": str(candidate_preview)},
        )
    )
    brief_path = root / "brief.json"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(
        json.dumps(
            {
                "brief_status": "ready",
                "note_count": 1,
                "reason_tag_counts": {"spacing-too-wide": 1},
                "primary_notes": ["字間が広い"],
                "selected_note_examples": [
                    {
                        "experiment_id": "exp-a",
                        "decision": "needs-tuning",
                        "reason_tags": ["spacing-too-wide"],
                        "notes": "字間が広い",
                        "reviewer_id": "reviewer-1",
                    }
                ],
                "top_reason_tags": ["spacing-too-wide"],
                "focus_lines": ["notes の指摘をそのまま次回の修正に反映する"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluation_harness",
            "human-feedback-preview-revision-run",
            "--root",
            str(root),
            "--brief-json",
            str(brief_path),
            "--focus-areas",
            "layout",
            "--max-items",
            "1",
            "--output",
            "preview-run.md",
            "--json-output",
            "preview-run.json",
        ],
    )

    from evaluation_harness.cli import main

    main()

    json_text = (root / "preview-run.json").read_text(encoding="utf-8")

    assert '"rerun_count": 1' in json_text
    assert '"rerun_plan_count": 1' in json_text


def test_abx_revision_run_command_writes_reports(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    candidate_preview = tmp_path / "preview.png"
    candidate_preview.write_bytes(b"candidate-preview")
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-motion-symbol",
            input_text="，",
            seed=1,
            generator="structure-motion",
            profile_id="symbol-neat",
            artifacts={"preview": str(candidate_preview)},
            metrics={
                "draw_speed_cv": 0.16,
                "baseline_drift_mm": 0.24,
                "penup_distance_mm": 13.2,
                "visible_char_count": 1,
            },
            failure_tags=["spacing-too-wide"],
        )
    )

    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "，",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            }
        ]
    }
    packet_json = root / "human_abx_packet.json"
    packet_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "abx-revision-run",
            "--root",
            str(root),
            "--packet-json",
            str(packet_json),
            "--output",
            "abx_revision_run.md",
            "--json-output",
            "abx_revision_run.json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    markdown = (root / "abx_revision_run.md").read_text(encoding="utf-8")
    json_text = (root / "abx_revision_run.json").read_text(encoding="utf-8")
    assert "ABX Revision Run" in markdown
    assert '"rerun_count"' in json_text
    assert '"preview_changed_count"' in json_text
    assert '"preview_changed": true' in json_text


def test_human_abx_bundle_command_writes_reports(tmp_path: Path) -> None:
    baseline_preview = tmp_path / "baseline.png"
    candidate_preview = tmp_path / "candidate.png"
    baseline_preview.write_bytes(b"baseline")
    candidate_preview.write_bytes(b"candidate")

    recommendation_path = tmp_path / "wide_recommendation.json"
    recommendation_path.write_text(
        json.dumps(
            {
                "baseline_generator": "baseline-outline",
                "expected_input_texts": ["日本"],
                "expected_seeds": [1],
                "expected_group_count": 1,
                "selected_candidate_count": 1,
                "selected_coverage_ratio": 1.0,
                "selected_profile_counts": {"textured-casual": 1},
                "candidate_profile_counts": {"textured-casual": 1},
                "focus_area_counts": {"layout": 1},
                "recommended_action_counts": {"character advance と line spacing を詰める": 1},
                "preview_comparisons": [
                    {
                        "input_text": "日本",
                        "seed": 1,
                        "baseline_experiment_id": "exp-baseline",
                        "baseline_preview": {"path": str(baseline_preview)},
                        "candidate_experiment_id": "exp-candidate",
                        "candidate_preview": {"path": str(candidate_preview)},
                        "preview_comparable": True,
                        "preview_hash_changed": True,
                        "preview_similarity": {"score": 1.0},
                        "preview_size_delta": 0,
                    }
                ],
                "recommendations": [
                    {
                        "input_text": "日本",
                        "seed": 1,
                        "baseline_experiment_id": "exp-baseline",
                        "selection_status": "selected",
                        "selected_candidate": {
                            "experiment_id": "exp-candidate",
                            "profile_id": "textured-casual",
                            "preview": {"path": str(candidate_preview)},
                            "inferred_failure_tags": ["spacing-too-wide"],
                            "suggested_next_actions": ["character advance と line spacing を詰める"],
                            "focus_area": "layout",
                        },
                        "candidate_count": 1,
                        "preview_candidate_count": 1,
                        "candidate_items": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle",
            "--recommendation-json",
            str(recommendation_path),
            "--focus-areas",
            "layout",
            "--max-items",
            "1",
            "--output-dir",
            "bundle",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    bundle_dir = tmp_path / "bundle"
    assert (bundle_dir / "layout_abx_packet.md").exists()
    assert (bundle_dir / "layout_abx_packet.json").exists()
    assert (bundle_dir / "layout_abx_workbook.md").exists()
    assert (bundle_dir / "layout_abx_workbook.json").exists()
    assert (bundle_dir / "layout_abx_feedback_loop.md").exists()
    assert (bundle_dir / "layout_abx_feedback_loop.json").exists()
    assert (bundle_dir / "layout_abx_response_template.json").exists()
    assert (bundle_dir / "layout_abx_responses.json").exists()


def test_human_abx_bundle_followup_command_uses_bundle_defaults(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    bundle_dir = root / "layout_bundle_v1"
    bundle_dir.mkdir(parents=True)

    candidate_preview = tmp_path / "preview.png"
    candidate_preview.write_bytes(b"candidate-preview")
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-motion-symbol",
            input_text="，",
            seed=1,
            generator="structure-motion",
            profile_id="symbol-neat",
            artifacts={"preview": str(candidate_preview)},
            metrics={
                "draw_speed_cv": 0.16,
                "baseline_drift_mm": 0.24,
                "penup_distance_mm": 13.2,
                "visible_char_count": 1,
            },
            failure_tags=["spacing-too-wide"],
        )
    )

    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "，",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            }
        ]
    }
    packet_json = bundle_dir / "layout_abx_packet.json"
    packet_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    workbook_json = bundle_dir / "layout_abx_workbook.json"
    workbook_json.write_text(
        json.dumps(
            {
                "evaluator_id": "eval-1",
                "rows": [
                    {
                        "item_id": "item-1",
                        "prompt": "，",
                        "candidate_profile_id": "symbol-neat",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "B",
                        "confidence": 4,
                        "note": "more natural",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-followup",
            "--root",
            str(root),
            "--bundle-dir",
            str(bundle_dir),
            "--bundle-prefix",
            "layout_abx",
            "--output-prefix",
            "layout_abx_followup",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (bundle_dir / "layout_abx_followup_response_summary.md").exists()
    assert (bundle_dir / "layout_abx_followup_response_summary.json").exists()
    assert (bundle_dir / "layout_abx_followup_feedback_loop.md").exists()
    assert (bundle_dir / "layout_abx_followup_feedback_loop.json").exists()
    assert (bundle_dir / "layout_abx_followup_revision_plan.md").exists()
    assert (bundle_dir / "layout_abx_followup_revision_plan.json").exists()
    assert (bundle_dir / "layout_abx_followup_revision_run.md").exists()
    assert (bundle_dir / "layout_abx_followup_revision_run.json").exists()
    assert (bundle_dir / "layout_abx_followup_responses.json").exists()
    assert "completed_row_count: 1" in result.stdout
    assert "completion_ratio: 1.0" in result.stdout
    assert "responses_json:" in result.stdout
    run_json = json.loads((bundle_dir / "layout_abx_followup_revision_run.json").read_text(encoding="utf-8"))
    assert run_json["rerun_count"] == 1
    assert run_json["preview_changed_count"] == 1
    responses_json = json.loads((bundle_dir / "layout_abx_followup_responses.json").read_text(encoding="utf-8"))
    assert responses_json["responses"][0]["choice"] == "B"


def test_human_abx_bundle_followup_command_writes_pending_workbook(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    bundle_dir = root / "layout_bundle_v1"
    bundle_dir.mkdir(parents=True)

    candidate_preview = tmp_path / "preview.png"
    candidate_preview.write_bytes(b"candidate-preview")
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-motion-symbol",
            input_text="，",
            seed=1,
            generator="structure-motion",
            profile_id="symbol-neat",
            artifacts={"preview": str(candidate_preview)},
            metrics={
                "draw_speed_cv": 0.16,
                "baseline_drift_mm": 0.24,
                "penup_distance_mm": 13.2,
                "visible_char_count": 1,
            },
            failure_tags=["spacing-too-wide"],
        )
    )

    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "，",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
            {
                "item_id": "item-2",
                "prompt": "字間",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "layout-tight",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
        ]
    }
    (bundle_dir / "layout_abx_packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    workbook_json = bundle_dir / "layout_abx_workbook.json"
    workbook_json.write_text(
        json.dumps(
            {
                "evaluator_id": "eval-1",
                "rows": [
                    {
                        "item_id": "item-1",
                        "prompt": "，",
                        "candidate_profile_id": "symbol-neat",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "B",
                        "confidence": 4,
                        "note": "more natural",
                    },
                    {
                        "item_id": "item-2",
                        "prompt": "字間",
                        "candidate_profile_id": "layout-tight",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "",
                        "confidence": "",
                        "note": "",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-followup",
            "--root",
            str(root),
            "--bundle-dir",
            str(bundle_dir),
            "--bundle-prefix",
            "layout_abx",
            "--pending-only",
            "--output-prefix",
            "layout_abx_followup",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (bundle_dir / "layout_abx_followup_pending_packet.md").exists()
    assert (bundle_dir / "layout_abx_followup_pending_packet.json").exists()
    pending_workbook = json.loads((bundle_dir / "layout_abx_followup_pending_workbook.json").read_text(encoding="utf-8"))
    assert len(pending_workbook["rows"]) == 1
    assert pending_workbook["rows"][0]["item_id"] == "item-2"
    pending_packet = json.loads((bundle_dir / "layout_abx_followup_pending_packet.json").read_text(encoding="utf-8"))
    assert len(pending_packet["abx_items"]) == 1
    assert pending_packet["abx_items"][0]["item_id"] == "item-2"
    assert "pending_packet_rows: 1" in result.stdout
    assert "pending_workbook_rows: 1" in result.stdout


def test_human_abx_bundle_followup_command_writes_next_bundle(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    bundle_dir = root / "layout_bundle_v1"
    next_bundle_dir = root / "layout_bundle_v2"
    bundle_dir.mkdir(parents=True)

    candidate_preview = tmp_path / "preview.png"
    candidate_preview.write_bytes(b"candidate-preview")
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-motion-symbol",
            input_text="，",
            seed=1,
            generator="structure-motion",
            profile_id="symbol-neat",
            artifacts={"preview": str(candidate_preview)},
            metrics={
                "draw_speed_cv": 0.16,
                "baseline_drift_mm": 0.24,
                "penup_distance_mm": 13.2,
                "visible_char_count": 1,
            },
            failure_tags=["spacing-too-wide"],
        )
    )

    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "，",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
            {
                "item_id": "item-2",
                "prompt": "字間",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "layout-tight",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
        ]
    }
    (bundle_dir / "layout_abx_packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "layout_abx_workbook.json").write_text(
        json.dumps(
            {
                "evaluator_id": "eval-1",
                "rows": [
                    {
                        "item_id": "item-1",
                        "prompt": "，",
                        "candidate_profile_id": "symbol-neat",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "B",
                        "confidence": 4,
                        "note": "more natural",
                    },
                    {
                        "item_id": "item-2",
                        "prompt": "字間",
                        "candidate_profile_id": "layout-tight",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "",
                        "confidence": "",
                        "note": "",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-followup",
            "--root",
            str(root),
            "--bundle-dir",
            str(bundle_dir),
            "--bundle-prefix",
            "layout_abx",
            "--pending-only",
            "--next-bundle-dir",
            str(next_bundle_dir),
            "--next-bundle-prefix",
            "layout_abx_v2",
            "--output-prefix",
            "layout_abx_followup",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (next_bundle_dir / "layout_abx_v2_packet.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_workbook.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_feedback_loop.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_response_template.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_responses.json").exists()
    assert "next_bundle_dir:" in result.stdout
    assert "next_bundle_prefix: layout_abx_v2" in result.stdout


def test_human_abx_bundle_followup_command_chains_next_bundle(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    bundle_dir = root / "layout_bundle_v1"
    next_bundle_dir = root / "layout_bundle_v2"
    bundle_dir.mkdir(parents=True)

    candidate_preview = tmp_path / "preview.png"
    candidate_preview.write_bytes(b"candidate-preview")
    registry = ExperimentRegistry(root / "registry.jsonl")
    registry.append(
        _record(
            experiment_id="exp-motion-symbol",
            input_text="，",
            seed=1,
            generator="structure-motion",
            profile_id="symbol-neat",
            artifacts={"preview": str(candidate_preview)},
            metrics={
                "draw_speed_cv": 0.16,
                "baseline_drift_mm": 0.24,
                "penup_distance_mm": 13.2,
                "visible_char_count": 1,
            },
            failure_tags=["spacing-too-wide"],
        )
    )

    packet = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "，",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "symbol-neat",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
            {
                "item_id": "item-2",
                "prompt": "字間",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "layout-tight",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            },
        ]
    }
    (bundle_dir / "layout_abx_packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (bundle_dir / "layout_abx_workbook.json").write_text(
        json.dumps(
            {
                "evaluator_id": "eval-1",
                "rows": [
                    {
                        "item_id": "item-1",
                        "prompt": "，",
                        "candidate_profile_id": "symbol-neat",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "B",
                        "confidence": 4,
                        "note": "more natural",
                    },
                    {
                        "item_id": "item-2",
                        "prompt": "字間",
                        "candidate_profile_id": "layout-tight",
                        "selected_failure_tags": ["spacing-too-wide"],
                        "selected_next_actions": ["character advance と line spacing を詰める"],
                        "choice": "",
                        "confidence": "",
                        "note": "",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-followup",
            "--root",
            str(root),
            "--bundle-dir",
            str(bundle_dir),
            "--bundle-prefix",
            "layout_abx_v1",
            "--pending-only",
            "--chain-next-bundle",
            "--output-prefix",
            "layout_abx_followup",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (next_bundle_dir / "layout_abx_v2_packet.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_workbook.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_feedback_loop.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_response_template.json").exists()
    assert (next_bundle_dir / "layout_abx_v2_responses.json").exists()
    assert "next_bundle_dir:" in result.stdout
    assert "next_bundle_prefix: layout_abx_v2" in result.stdout


def test_human_abx_bundle_chain_status_command_writes_summary(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "runs" / "layout_bundle_v1"
    next_bundle_dir = tmp_path / "runs" / "layout_bundle_v2"
    bundle_dir.mkdir(parents=True)
    next_bundle_dir.mkdir(parents=True)

    packet_v1 = {
        "abx_items": [
            {
                "item_id": "item-1",
                "prompt": "字間",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "layout-tight",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-motion-symbol",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            }
        ]
    }
    workbook_v1 = {
        "evaluator_id": "eval-1",
        "rows": [
            {
                "item_id": "item-1",
                "prompt": "字間",
                "candidate_profile_id": "layout-tight",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
                "choice": "",
                "confidence": "",
                "note": "",
            }
        ],
    }
    packet_v2 = {
        "abx_items": [
            {
                "item_id": "item-2",
                "prompt": "提出",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "kanji-tight",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-motion-symbol-2",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": ["terminal-too-uniform"],
                "selected_next_actions": ["terminal 表現を強める"],
            }
        ]
    }
    workbook_v2 = {
        "evaluator_id": "eval-1",
        "rows": [
            {
                "item_id": "item-2",
                "prompt": "提出",
                "candidate_profile_id": "kanji-tight",
                "selected_failure_tags": ["terminal-too-uniform"],
                "selected_next_actions": ["terminal 表現を強める"],
                "choice": "A",
                "confidence": 5,
                "note": "better spacing",
            }
        ],
    }
    (bundle_dir / "layout_abx_packet.json").write_text(
        json.dumps(packet_v1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "layout_abx_workbook.json").write_text(
        json.dumps(workbook_v1, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (next_bundle_dir / "layout_abx_v2_packet.json").write_text(
        json.dumps(packet_v2, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (next_bundle_dir / "layout_abx_v2_workbook.json").write_text(
        json.dumps(workbook_v2, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-chain-status",
            "--bundle-dir",
            str(bundle_dir),
            "--bundle-prefix",
            "layout_abx",
            "--max-depth",
            "4",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bundle_count: 2" in result.stdout
    assert "open_bundle_count: 1" in result.stdout
    assert (bundle_dir / "bundle_chain_status.md").exists()
    assert (bundle_dir / "bundle_chain_status.json").exists()
    status_json = json.loads((bundle_dir / "bundle_chain_status.json").read_text(encoding="utf-8"))
    assert status_json["bundle_count"] == 2
    assert status_json["bundles"][0]["pending_row_count"] == 1
    assert status_json["bundles"][1]["completed_row_count"] == 1
    assert status_json["bundles"][1]["revision_rerun_count"] == 0
    assert status_json["bundles"][1]["revision_preview_changed_count"] == 0


def test_human_abx_bundle_sweep_status_command_writes_summary(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    layout_v1 = root / "layout_bundle_v1"
    motion_v1 = root / "motion_bundle_v1"
    layout_v1.mkdir(parents=True)
    motion_v1.mkdir(parents=True)

    layout_packet = {
        "abx_items": [
            {
                "item_id": "layout-1",
                "prompt": "字間",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "layout-tight",
                "baseline_experiment_id": "exp-baseline",
                "candidate_experiment_id": "exp-layout",
                "option_a_artifact": "a.png",
                "option_b_artifact": "b.png",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
            }
        ]
    }
    layout_workbook = {
        "evaluator_id": "eval-1",
        "rows": [
            {
                "item_id": "layout-1",
                "prompt": "字間",
                "candidate_profile_id": "layout-tight",
                "selected_failure_tags": ["spacing-too-wide"],
                "selected_next_actions": ["character advance と line spacing を詰める"],
                "choice": "",
                "confidence": "",
                "note": "",
            }
        ],
    }
    motion_packet = {
        "abx_items": [
            {
                "item_id": "motion-1",
                "prompt": "提出",
                "question": "どちらが人間の手書きに近いか",
                "candidate_profile_id": "kanji-tight",
                "baseline_experiment_id": "exp-baseline-2",
                "candidate_experiment_id": "exp-motion",
                "option_a_artifact": "a2.png",
                "option_b_artifact": "b2.png",
                "selected_failure_tags": ["terminal-too-uniform"],
                "selected_next_actions": ["terminal 表現を強める"],
            }
        ]
    }
    motion_workbook = {
        "evaluator_id": "eval-1",
        "rows": [
            {
                "item_id": "motion-1",
                "prompt": "提出",
                "candidate_profile_id": "kanji-tight",
                "selected_failure_tags": ["terminal-too-uniform"],
                "selected_next_actions": ["terminal 表現を強める"],
                "choice": "A",
                "confidence": 5,
                "note": "better spacing",
            }
        ],
    }
    (layout_v1 / "layout_abx_packet.json").write_text(
        json.dumps(layout_packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (layout_v1 / "layout_abx_workbook.json").write_text(
        json.dumps(layout_workbook, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (motion_v1 / "motion_abx_packet.json").write_text(
        json.dumps(motion_packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (motion_v1 / "motion_abx_workbook.json").write_text(
        json.dumps(motion_workbook, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation_harness.cli",
            "human-abx-bundle-sweep-status",
            "--root",
            str(root),
            "--max-depth",
            "4",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bundle_root_count: 2" in result.stdout
    assert "open_bundle_root_count: 1" in result.stdout
    assert (root / "bundle_sweep_status.md").exists()
    assert (root / "bundle_sweep_status.json").exists()
    sweep_json = json.loads((root / "bundle_sweep_status.json").read_text(encoding="utf-8"))
    assert sweep_json["bundle_root_count"] == 2
    assert sweep_json["bundle_chains"][0]["bundle_count"] == 1
    assert sweep_json["bundle_chains"][1]["bundle_count"] == 1
    assert sweep_json["bundle_chains"][0]["bundles"][0]["revision_rerun_count"] == 0
    assert sweep_json["bundle_chains"][1]["bundles"][0]["revision_preview_changed_count"] == 0
    assert len(sweep_json["ranked_bundle_chains"]) == 2


def _record(
    *,
    experiment_id: str,
    input_text: str,
    seed: int,
    generator: str,
    profile_id: str = "baseline-neat",
    artifacts: dict[str, str] | None = None,
    metrics: dict[str, float | int | str] | None = None,
    failure_tags: list[str] | None = None,
) -> ExperimentRecord:
    resolved_artifacts = {"report": f"artifacts/{experiment_id}/report.md"}
    if artifacts:
        resolved_artifacts.update(artifacts)
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id=profile_id,
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts=resolved_artifacts,
        metrics=metrics or {"duration_ms": 1000, "stroke_count": 1},
        failure_tags=failure_tags or [],
        next_action="validate fixed input comparison",
    )

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
    assert "completed_row_count: 1" in result.stdout
    assert "completion_ratio: 1.0" in result.stdout
    run_json = json.loads((bundle_dir / "layout_abx_followup_revision_run.json").read_text(encoding="utf-8"))
    assert run_json["rerun_count"] == 1
    assert run_json["preview_changed_count"] == 1


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

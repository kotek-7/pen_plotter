from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from evaluation_harness.artifacts import ArtifactStore
from evaluation_harness.baseline_outline import (
    BaselineOutlineConfig,
    run_baseline_outline,
    run_baseline_outline_batch,
)
from evaluation_harness.evaluation_inputs import get_evaluation_inputs
from evaluation_harness.compare import (
    compare_against_baseline,
    compare_fixed_input_set,
    compare_preview_fixed_input_set,
    recommend_preview_fixed_input_set,
    propose_preview_fixed_input_set,
    render_comparison_markdown,
    render_fixed_input_comparison_markdown,
    render_preview_fixed_input_comparison_markdown,
    render_preview_iteration_markdown,
    render_preview_recommendation_markdown,
    render_preview_revision_plan_markdown,
    preview_iteration_fixed_input_set,
)
from evaluation_harness.revision_loop import (
    evaluate_data_driven_writer_prior_fixed_input_set,
    render_preview_revision_loop_markdown,
    render_preview_revision_loop_summary_markdown,
    render_data_driven_writer_prior_evaluation_markdown,
    render_stable_writer_profile_evaluation_markdown,
    render_stable_writer_profile_candidates_markdown,
    propose_stable_writer_profile_candidates,
    evaluate_stable_writer_profile_candidates,
    run_preview_revision_loop_fixed_input_set,
    summarize_preview_revision_loops,
)
from evaluation_harness.self_check import render_self_check_markdown, run_self_check
from evaluation_harness.human_review import (
    build_human_review_packet,
    render_human_review_packet_markdown,
)
from evaluation_harness.human_feedback_loop import (
    build_human_feedback_loop,
    render_human_feedback_loop_markdown,
)
from evaluation_harness.human_abx import (
    build_human_abx_packet,
    build_human_abx_feedback_loop,
    render_abx_feedback_loop_markdown,
    render_human_abx_packet_markdown,
)
from evaluation_harness.abx import (
    AbxItem,
    build_abx_pending_packet,
    build_abx_revision_plan,
    build_abx_responses_from_workbook,
    build_abx_workbook,
    load_abx_responses,
    render_abx_revision_plan_markdown,
    render_abx_revision_run_markdown,
    render_abx_summary_markdown,
    render_abx_workbook_markdown,
    run_abx_revision_loop,
    summarize_abx_workbook_completion,
    summarize_abx_responses,
)
from evaluation_harness.human_review_response import (
    build_human_review_revision_brief,
    build_human_review_preview_revision_plan,
    build_human_review_revision_plan,
    load_human_review_responses,
    render_human_review_response_markdown,
    render_human_review_preview_revision_plan_markdown,
    render_human_review_revision_brief_markdown,
    render_human_review_revision_plan_markdown,
    summarize_human_review_responses,
)
from evaluation_harness.metrics import compute_trajectory_metrics
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import build_offline_review, render_offline_review_markdown
from evaluation_harness.plot_ready import build_plot_ready_packet, render_plot_ready_packet_markdown
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.report import render_markdown_report
from evaluation_harness.scan import ScanMetadata, attach_scan_artifact
from evaluation_harness.structure_uniform import (
    DEFAULT_STRUCTURE_INPUTS,
    EVALUATION_STRUCTURE_INPUTS,
    EXTENDED_STRUCTURE_INPUTS,
    REVIEW_STRUCTURE_INPUTS,
    WIDE_STRUCTURE_INPUTS,
    StructureUniformConfig,
    run_structure_uniform,
    run_structure_uniform_batch,
)
from evaluation_harness.goal_audit import render_goal_audit_markdown, run_goal_audit
from evaluation_harness.structure_motion import (
    StructureMotionConfig,
    run_structure_motion,
    run_structure_motion_batch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scribing Lab evaluation harness")
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="Create one baseline registry entry and report")
    smoke.add_argument("--root", default="runs", help="Run output directory")
    smoke.add_argument("--experiment-id", default="exp-000001")
    smoke.add_argument("--input-text", default="永")

    baseline = sub.add_parser(
        "baseline-outline",
        help="Run the fixed font-outline baseline and register artifacts",
    )
    baseline.add_argument("--root", default="runs/baseline-outline", help="Run output directory")
    baseline.add_argument("--experiment-id", default="exp-baseline-000001")
    baseline.add_argument("--input-text", default="永")
    baseline.add_argument("--seed", type=int, default=1)
    baseline.add_argument("--profile-id", default="baseline-neat")
    baseline.add_argument("--font-size", type=float, default=7.0)
    baseline.add_argument("--jitter", type=float, default=0.08)
    baseline.add_argument("--wobble", type=float, default=0.04)
    baseline.add_argument("--no-optimize", action="store_true")
    baseline.add_argument("--no-vary-speed", action="store_true")

    batch = sub.add_parser(
        "baseline-outline-batch",
        help="Run baseline-outline for the fixed evaluation input set",
    )
    batch.add_argument("--root", default="runs/baseline-outline", help="Run output directory")
    batch.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    batch.add_argument("--profile-id", default="baseline-neat")
    batch.add_argument("--experiment-prefix", default="exp-baseline")
    batch.add_argument("--font-size", type=float, default=7.0)
    batch.add_argument("--jitter", type=float, default=0.08)
    batch.add_argument("--wobble", type=float, default=0.04)
    batch.add_argument("--no-optimize", action="store_true")
    batch.add_argument("--no-vary-speed", action="store_true")
    batch.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )

    compare = sub.add_parser("compare", help="Compare registered experiments against a baseline")
    compare.add_argument("--root", default="runs/baseline-outline", help="Run output directory")
    compare.add_argument("--baseline-generator", default="baseline-outline")
    compare.add_argument("--output", default="comparison_report.md")

    fixed_compare = sub.add_parser(
        "compare-fixed-inputs",
        help="Compare the fixed evaluation input set against a baseline generator",
    )
    fixed_compare.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    fixed_compare.add_argument("--baseline-generator", default="baseline-outline")
    fixed_compare.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    fixed_compare.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    fixed_compare.add_argument("--output", default="fixed_input_comparison.md")
    fixed_compare.add_argument("--json-output", default="fixed_input_comparison.json")

    preview_compare = sub.add_parser(
        "compare-preview-fixed-inputs",
        help="Compare preview artifacts for the fixed evaluation input set",
    )
    preview_compare.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    preview_compare.add_argument("--baseline-generator", default="baseline-outline")
    preview_compare.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    preview_compare.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    preview_compare.add_argument("--output", default="preview_input_comparison.md")
    preview_compare.add_argument("--json-output", default="preview_input_comparison.json")

    preview_recommend = sub.add_parser(
        "recommend-preview-fixed-inputs",
        help="Select preview candidates and propose the next change set",
    )
    preview_recommend.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    preview_recommend.add_argument("--baseline-generator", default="baseline-outline")
    preview_recommend.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    preview_recommend.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    preview_recommend.add_argument("--output", default="preview_recommendation.md")
    preview_recommend.add_argument("--json-output", default="preview_recommendation.json")

    preview_propose = sub.add_parser(
        "propose-preview-fixed-inputs",
        help="Generate revision plans from preview-selected candidates",
    )
    preview_propose.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    preview_propose.add_argument("--baseline-generator", default="baseline-outline")
    preview_propose.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    preview_propose.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    preview_propose.add_argument("--output", default="preview_revision_plan.md")
    preview_propose.add_argument("--json-output", default="preview_revision_plan.json")

    preview_iteration = sub.add_parser(
        "preview-iteration-fixed-inputs",
        help="Run one preview-driven experiment iteration for the fixed input set",
    )
    preview_iteration.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    preview_iteration.add_argument("--baseline-generator", default="baseline-outline")
    preview_iteration.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    preview_iteration.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    preview_iteration.add_argument("--output", default="preview_iteration.md")
    preview_iteration.add_argument("--json-output", default="preview_iteration.json")

    preview_apply = sub.add_parser(
        "apply-preview-revision-fixed-inputs",
        help="Apply preview revision plans and rerun the fixed input set",
    )
    preview_apply.add_argument(
        "--root",
        default="runs/baseline-outline",
        help="Run output directory",
    )
    preview_apply.add_argument("--baseline-generator", default="baseline-outline")
    preview_apply.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    preview_apply.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    preview_apply.add_argument(
        "--revision-plan-json",
        help="Use an explicit revision plan JSON instead of recomputing from the registry",
    )
    preview_apply.add_argument("--output", default="preview_revision_loop.md")
    preview_apply.add_argument("--json-output", default="preview_revision_loop.json")

    preview_loop_summary = sub.add_parser(
        "summarize-preview-revision-loops",
        help="Summarize multiple preview revision loop packets",
    )
    preview_loop_summary.add_argument(
        "--packet-json",
        nargs="+",
        required=True,
        help="One or more preview revision loop JSON packets",
    )
    preview_loop_summary.add_argument("--output", default="preview_revision_loop_summary.md")
    preview_loop_summary.add_argument("--json-output", default="preview_revision_loop_summary.json")

    stable_profiles = sub.add_parser(
        "propose-stable-writer-profiles",
        help="Build stable writer profile candidates from a revision loop summary",
    )
    stable_profiles.add_argument("--summary-json", required=True)
    stable_profiles.add_argument("--base-profile-id", default="baseline-neat")
    stable_profiles.add_argument("--output", default="stable_writer_profiles.md")
    stable_profiles.add_argument("--json-output", default="stable_writer_profiles.json")

    stable_profile_evaluation = sub.add_parser(
        "evaluate-stable-writer-profiles",
        help="Evaluate stable writer profile candidates against the fixed input set",
    )
    stable_profile_evaluation.add_argument("--summary-json", required=True)
    stable_profile_evaluation.add_argument("--root", required=True, help="Run output directory")
    stable_profile_evaluation.add_argument("--base-profile-id", default="baseline-neat")
    stable_profile_evaluation.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    stable_profile_evaluation.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    stable_profile_evaluation.add_argument("--output", default="stable_writer_profile_evaluation.md")
    stable_profile_evaluation.add_argument(
        "--json-output",
        default="stable_writer_profile_evaluation.json",
    )

    data_prior_evaluation = sub.add_parser(
        "evaluate-data-driven-writer-prior",
        help="Evaluate a data-driven prior against the fixed input set",
    )
    data_prior_evaluation.add_argument("--samples-jsonl", required=True)
    data_prior_evaluation.add_argument("--root", required=True, help="Run output directory")
    data_prior_evaluation.add_argument("--base-profile-id", default="baseline-neat")
    data_prior_evaluation.add_argument("--seeds", default="1,2,3", help="Comma-separated integer seeds")
    data_prior_evaluation.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="fixed",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    data_prior_evaluation.add_argument("--output", default="data_driven_prior_evaluation.md")
    data_prior_evaluation.add_argument(
        "--json-output",
        default="data_driven_prior_evaluation.json",
    )

    offline_review = sub.add_parser(
        "offline-review",
        help="Review registered experiments from artifacts and metrics without plotted scans",
    )
    offline_review.add_argument("--root", required=True, help="Run output directory")
    offline_review.add_argument("--output", default="offline_review.md")
    offline_review.add_argument("--json-output", default="offline_review.json")

    human_review = sub.add_parser(
        "human-review-packet",
        help="Create a compact preview and metrics packet for pre-plot human review",
    )
    human_review.add_argument("--root", required=True, help="Run output directory")
    human_review.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Target number of representative items to include in the packet",
    )
    human_review.add_argument("--output", default="human_review_packet.md")
    human_review.add_argument("--json-output", default="human_review_packet.json")

    human_feedback = sub.add_parser(
        "human-feedback-loop",
        help="Create a human subjective feedback loop packet and optional response summary",
    )
    human_feedback.add_argument("--root", required=True, help="Run output directory")
    human_feedback.add_argument("--responses-json", help="Human review response JSON")
    human_feedback.add_argument("--reviewer-id", default="")
    human_feedback.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Target number of representative items to include in the packet",
    )
    human_feedback.add_argument(
        "--brief-only",
        action="store_true",
        help="Emit a revision brief focused on notes and top reason tags",
    )
    human_feedback.add_argument("--output", default="human_feedback_loop.md")
    human_feedback.add_argument("--json-output", default="human_feedback_loop.json")
    human_feedback.add_argument("--brief-output", default="human_review_revision_brief.md")
    human_feedback.add_argument("--brief-json-output", default="human_review_revision_brief.json")

    human_feedback_ui = sub.add_parser(
        "human-feedback-ui",
        help="Launch a Qt human review UI for the feedback loop",
    )
    target = human_feedback_ui.add_mutually_exclusive_group(required=True)
    target.add_argument("--root", help="Run output directory")
    target.add_argument("--packet-json", help="Existing review packet or loop JSON")
    human_feedback_ui.add_argument("--responses-json", help="Existing human responses JSON")
    human_feedback_ui.add_argument("--summary-json", help="Human review summary output path")
    human_feedback_ui.add_argument("--brief-json", help="Human review revision brief JSON output path")
    human_feedback_ui.add_argument("--brief-markdown", help="Human review revision brief markdown output path")
    human_feedback_ui.add_argument("--plan-json", help="Human review revision plan JSON output path")
    human_feedback_ui.add_argument("--plan-markdown", help="Human review revision plan markdown output path")
    human_feedback_ui.add_argument("--preview-run-json", help="Human review preview revision run JSON output path")
    human_feedback_ui.add_argument("--preview-run-markdown", help="Human review preview revision run markdown output path")
    human_feedback_ui.add_argument("--reviewer-id", default="")
    human_feedback_ui.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Target number of representative items to include in the packet",
    )

    human_feedback_plan = sub.add_parser(
        "human-feedback-revision-plan",
        help="Generate a preview revision plan from a human feedback brief",
    )
    human_feedback_plan.add_argument("--brief-json", help="Human review revision brief JSON")
    human_feedback_plan.add_argument("--loop-json", help="Human feedback loop JSON")
    human_feedback_plan.add_argument("--output", default="human_review_revision_plan.md")
    human_feedback_plan.add_argument("--json-output", default="human_review_revision_plan.json")

    human_feedback_preview_plan = sub.add_parser(
        "human-feedback-preview-revision-plan",
        help="Generate a preview revision plan from a human review brief",
    )
    human_feedback_preview_plan.add_argument("--root", required=True, help="Run output directory")
    human_feedback_preview_plan.add_argument("--brief-json", help="Human review revision brief JSON")
    human_feedback_preview_plan.add_argument("--loop-json", help="Human feedback loop JSON")
    human_feedback_preview_plan.add_argument("--input-set", choices=("fixed", "review", "wide"), default="wide")
    human_feedback_preview_plan.add_argument("--seeds", default="1")
    human_feedback_preview_plan.add_argument("--baseline-generator", default="baseline-outline")
    human_feedback_preview_plan.add_argument("--output", default="human_review_preview_revision_plan.md")
    human_feedback_preview_plan.add_argument("--json-output", default="human_review_preview_revision_plan.json")

    human_feedback_preview_run = sub.add_parser(
        "human-feedback-preview-revision-run",
        help="Generate a preview revision plan from human feedback and rerun it",
    )
    human_feedback_preview_run.add_argument("--root", required=True, help="Run output directory")
    human_feedback_preview_run.add_argument("--brief-json", help="Human review revision brief JSON")
    human_feedback_preview_run.add_argument("--loop-json", help="Human feedback loop JSON")
    human_feedback_preview_run.add_argument("--input-set", choices=("fixed", "review", "wide"), default="wide")
    human_feedback_preview_run.add_argument("--seeds", default="1,2,3")
    human_feedback_preview_run.add_argument("--baseline-generator", default="baseline-outline")
    human_feedback_preview_run.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep when selecting preview revision plans",
    )
    human_feedback_preview_run.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Limit the number of preview revision plans to rerun",
    )
    human_feedback_preview_run.add_argument("--output", default="human_review_preview_revision_run.md")
    human_feedback_preview_run.add_argument("--json-output", default="human_review_preview_revision_run.json")

    preview_review = sub.add_parser(
        "preview-review-packet",
        help="Create a preview-centric packet for generated G-code review",
    )
    preview_review.add_argument("--root", required=True, help="Run output directory")
    preview_review.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Target number of representative items to include in the packet",
    )
    preview_review.add_argument("--output", default="preview_review_packet.md")
    preview_review.add_argument("--json-output", default="preview_review_packet.json")

    human_abx = sub.add_parser(
        "human-abx-packet",
        help="Create an ABX packet from preview-selected candidate pairs",
    )
    human_abx.add_argument("--root", default="", help="Run output directory")
    human_abx.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="wide",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    human_abx.add_argument("--seeds", default="1", help="Comma-separated integer seeds")
    human_abx.add_argument("--baseline-generator", default="baseline-outline")
    human_abx.add_argument(
        "--recommendation-json",
        default="",
        help="Reuse an existing preview recommendation JSON instead of recomputing it",
    )
    human_abx.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep, such as layout,motion",
    )
    human_abx.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Limit the number of ABX items after filtering",
    )
    human_abx.add_argument("--output", default="human_abx_packet.md")
    human_abx.add_argument("--json-output", default="human_abx_packet.json")

    human_abx_loop = sub.add_parser(
        "human-abx-feedback-loop",
        help="Summarize ABX responses and generate the next feedback loop packet",
    )
    human_abx_loop.add_argument("--packet-json", default="")
    human_abx_loop.add_argument("--recommendation-json", default="")
    human_abx_loop.add_argument("--responses-json", default="")
    human_abx_loop.add_argument("--evaluator-id", default="")
    human_abx_loop.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep when building a packet from recommendation JSON",
    )
    human_abx_loop.add_argument("--max-items", type=int, default=36)
    human_abx_loop.add_argument("--template-json-output", default="human_abx_response_template.json")
    human_abx_loop.add_argument("--output", default="human_abx_feedback_loop.md")
    human_abx_loop.add_argument("--json-output", default="human_abx_feedback_loop.json")

    human_abx_bundle = sub.add_parser(
        "human-abx-bundle",
        help="Create a focused ABX packet, workbook, and feedback bundle",
    )
    human_abx_bundle.add_argument("--root", default="", help="Run output directory")
    human_abx_bundle.add_argument(
        "--input-set",
        choices=("fixed", "review", "wide"),
        default="wide",
        help="Use the fixed, review, or wide evaluation corpus",
    )
    human_abx_bundle.add_argument("--seeds", default="1", help="Comma-separated integer seeds")
    human_abx_bundle.add_argument("--baseline-generator", default="baseline-outline")
    human_abx_bundle.add_argument("--packet-json", default="")
    human_abx_bundle.add_argument("--recommendation-json", default="")
    human_abx_bundle.add_argument("--responses-json", default="")
    human_abx_bundle.add_argument("--evaluator-id", default="")
    human_abx_bundle.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep, such as layout,motion",
    )
    human_abx_bundle.add_argument("--max-items", type=int, default=36)
    human_abx_bundle.add_argument("--output-dir", default="")
    human_abx_bundle.add_argument("--output-prefix", default="")

    human_abx_bundle_followup = sub.add_parser(
        "human-abx-bundle-followup",
        help="Summarize bundle responses and run the revision loop from a bundle directory",
    )
    human_abx_bundle_followup.add_argument("--root", required=True, help="Run output directory")
    human_abx_bundle_followup.add_argument("--bundle-dir", required=True, help="Bundle directory")
    human_abx_bundle_followup.add_argument("--bundle-prefix", required=True)
    human_abx_bundle_followup.add_argument("--workbook-json", default="")
    human_abx_bundle_followup.add_argument("--responses-json", default="")
    human_abx_bundle_followup.add_argument("--evaluator-id", default="")
    human_abx_bundle_followup.add_argument("--max-items", type=int, default=36)
    human_abx_bundle_followup.add_argument("--pending-only", action="store_true")
    human_abx_bundle_followup.add_argument("--next-bundle-dir", default="")
    human_abx_bundle_followup.add_argument("--next-bundle-prefix", default="")
    human_abx_bundle_followup.add_argument("--chain-next-bundle", action="store_true")
    human_abx_bundle_followup.add_argument("--output-prefix", default="")

    human_abx_bundle_chain_status = sub.add_parser(
        "human-abx-bundle-chain-status",
        help="Summarize the current bundle chain and pending ratios",
    )
    human_abx_bundle_chain_status.add_argument("--bundle-dir", required=True, help="Bundle directory")
    human_abx_bundle_chain_status.add_argument("--bundle-prefix", required=True)
    human_abx_bundle_chain_status.add_argument("--max-depth", type=int, default=8)
    human_abx_bundle_chain_status.add_argument("--output", default="bundle_chain_status.md")
    human_abx_bundle_chain_status.add_argument("--json-output", default="bundle_chain_status.json")

    human_abx_bundle_sweep_status = sub.add_parser(
        "human-abx-bundle-sweep-status",
        help="Summarize all bundle chains under a root directory",
    )
    human_abx_bundle_sweep_status.add_argument("--root", required=True, help="Run output directory")
    human_abx_bundle_sweep_status.add_argument("--max-depth", type=int, default=8)
    human_abx_bundle_sweep_status.add_argument("--output", default="bundle_sweep_status.md")
    human_abx_bundle_sweep_status.add_argument("--json-output", default="bundle_sweep_status.json")

    abx_workbook = sub.add_parser(
        "abx-workbook",
        help="Create a fillable ABX workbook from a packet",
    )
    abx_workbook.add_argument("--packet-json", default="")
    abx_workbook.add_argument("--recommendation-json", default="")
    abx_workbook.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep when building a packet from recommendation JSON",
    )
    abx_workbook.add_argument("--responses-json", default="")
    abx_workbook.add_argument("--evaluator-id", default="")
    abx_workbook.add_argument("--max-items", type=int, default=36)
    abx_workbook.add_argument("--output", default="abx_workbook.md")
    abx_workbook.add_argument("--json-output", default="abx_workbook.json")
    abx_workbook.add_argument("--responses-output", default="abx_responses.json")

    abx_revision = sub.add_parser(
        "abx-revision-plan",
        help="Generate a preview revision plan from an ABX feedback loop",
    )
    abx_revision.add_argument("--feedback-loop-json", default="")
    abx_revision.add_argument("--packet-json", default="")
    abx_revision.add_argument("--recommendation-json", default="")
    abx_revision.add_argument("--responses-json", default="")
    abx_revision.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep when building a packet from recommendation JSON",
    )
    abx_revision.add_argument("--max-items", type=int, default=36)
    abx_revision.add_argument("--evaluator-id", default="")
    abx_revision.add_argument("--output", default="abx_revision_plan.md")
    abx_revision.add_argument("--json-output", default="abx_revision_plan.json")

    abx_run = sub.add_parser(
        "abx-revision-run",
        help="Apply an ABX revision plan and rerun the selected preview experiments",
    )
    abx_run.add_argument("--root", required=True, help="Run output directory")
    abx_run.add_argument("--feedback-loop-json", default="")
    abx_run.add_argument("--packet-json", default="")
    abx_run.add_argument("--recommendation-json", default="")
    abx_run.add_argument("--responses-json", default="")
    abx_run.add_argument(
        "--focus-areas",
        default="",
        help="Comma-separated focus areas to keep when building a packet from recommendation JSON",
    )
    abx_run.add_argument("--max-items", type=int, default=36)
    abx_run.add_argument("--evaluator-id", default="")
    abx_run.add_argument("--output", default="abx_revision_run.md")
    abx_run.add_argument("--json-output", default="abx_revision_run.json")

    validate_human = sub.add_parser(
        "validate-human-review",
        help="Validate and summarize human review responses against a review packet",
    )
    validate_human.add_argument("--packet-json", required=True)
    validate_human.add_argument("--responses-json", required=True)
    validate_human.add_argument("--output", default="human_review_response_summary.md")
    validate_human.add_argument("--json-output", default="human_review_response_summary.json")

    validate_abx = sub.add_parser(
        "validate-abx-responses",
        help="Validate and summarize ABX responses against an ABX packet",
    )
    validate_abx.add_argument("--packet-json", required=True)
    validate_abx.add_argument("--responses-json", required=True)
    validate_abx.add_argument("--output", default="abx_response_summary.md")
    validate_abx.add_argument("--json-output", default="abx_response_summary.json")

    plot_ready = sub.add_parser(
        "plot-ready-packet",
        help="Create a safe pre-plot packet from accepted human review responses",
    )
    plot_ready.add_argument("--root", required=True, help="Run output directory")
    plot_ready.add_argument("--human-summary-json", required=True)
    plot_ready.add_argument("--output", default="plot_ready_packet.md")
    plot_ready.add_argument("--json-output", default="plot_ready_packet.json")

    self_check = sub.add_parser(
        "self-check",
        help="Run the evaluation-harness self-check against fixed fixtures",
    )
    self_check.add_argument("--root", default="runs/self-check", help="Run output directory")
    self_check.add_argument("--seed", type=int, default=1)
    self_check.add_argument("--output", default="self_check.md")
    self_check.add_argument("--json-output", default="self_check.json")

    goal_audit = sub.add_parser(
        "goal-audit",
        help="Run the closeout audit against the layered evaluation loop",
    )
    goal_audit.add_argument("--root", default="runs/goal-audit", help="Run output directory")
    goal_audit.add_argument("--seed", type=int, default=1)
    goal_audit.add_argument("--output", default="goal_audit.md")
    goal_audit.add_argument("--json-output", default="goal_audit.json")

    scan = sub.add_parser("attach-scan", help="Attach plotted scan artifact to an experiment")
    scan.add_argument("--root", required=True, help="Run output directory")
    scan.add_argument("--experiment-id", required=True)
    scan.add_argument("--scan-path", required=True)
    scan.add_argument("--metadata-json", required=True)

    structure = sub.add_parser(
        "structure-uniform",
        help="Run the character-dictionary structure baseline",
    )
    structure.add_argument("--root", default="runs/structure-uniform", help="Run output directory")
    structure.add_argument("--experiment-id", default="exp-structure-000001")
    structure.add_argument("--input-text", default="永")
    structure.add_argument("--seed", type=int, default=1)
    structure.add_argument("--profile-id", default="baseline-neat")

    structure_batch = sub.add_parser(
        "structure-uniform-batch",
        help="Run structure-uniform for the supported dictionary input set",
    )
    structure_batch.add_argument("--root", default="runs/structure-uniform")
    structure_batch.add_argument("--seeds", default="1,2,3")
    structure_batch.add_argument("--profile-id", default="baseline-neat")
    structure_batch.add_argument("--experiment-prefix", default="exp-structure")
    structure_batch.add_argument(
        "--input-set",
        choices=("basic", "extended", "evaluation", "review", "wide"),
        default="review",
    )

    motion = sub.add_parser(
        "structure-motion",
        help="Run the structure skeleton with motion timing",
    )
    motion.add_argument("--root", default="runs/structure-motion", help="Run output directory")
    motion.add_argument("--experiment-id", default="exp-motion-000001")
    motion.add_argument("--input-text", default="永")
    motion.add_argument("--seed", type=int, default=1)
    motion.add_argument("--profile-id", default="baseline-neat")
    motion.add_argument("--shape-variation", type=float, default=0.0)
    motion.add_argument("--layout-variation", type=float, default=0.0)

    motion_batch = sub.add_parser(
        "structure-motion-batch",
        help="Run structure-motion for the supported dictionary input set",
    )
    motion_batch.add_argument("--root", default="runs/structure-motion")
    motion_batch.add_argument("--seeds", default="1,2,3")
    motion_batch.add_argument("--profile-id", default="baseline-neat")
    motion_batch.add_argument("--experiment-prefix", default="exp-motion")
    motion_batch.add_argument("--shape-variation", type=float, default=0.0)
    motion_batch.add_argument("--layout-variation", type=float, default=0.0)
    motion_batch.add_argument(
        "--input-set",
        choices=("basic", "extended", "evaluation", "review", "wide"),
        default="review",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "smoke":
        run_smoke(Path(args.root), args.experiment_id, args.input_text)
    elif args.command == "baseline-outline":
        record = run_baseline_outline(
            root=Path(args.root),
            experiment_id=args.experiment_id,
            input_text=args.input_text,
            seed=args.seed,
            profile_id=args.profile_id,
            config=BaselineOutlineConfig(
                font_size=args.font_size,
                jitter=args.jitter,
                wobble=args.wobble,
                optimize=not args.no_optimize,
                vary_speed=not args.no_vary_speed,
            ),
        )
        print(f"registered {record.experiment_id}")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"report: {record.artifacts['report']}")
    elif args.command == "baseline-outline-batch":
        records = run_baseline_outline_batch(
            root=Path(args.root),
            input_texts=get_evaluation_inputs(args.input_set),
            seeds=_parse_seeds(args.seeds),
            profile_id=args.profile_id,
            experiment_prefix=args.experiment_prefix,
            config=BaselineOutlineConfig(
                font_size=args.font_size,
                jitter=args.jitter,
                wobble=args.wobble,
                optimize=not args.no_optimize,
                vary_speed=not args.no_vary_speed,
            ),
        )
        print(f"registered {len(records)} experiments")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"summary: {Path(args.root) / 'summary.md'}")
    elif args.command == "compare":
        registry = ExperimentRegistry(Path(args.root) / "registry.jsonl")
        comparison = compare_against_baseline(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
        )
        output_path = Path(args.root) / args.output
        output_path.write_text(render_comparison_markdown(comparison), encoding="utf-8")
        print(f"comparison_count: {comparison['comparison_count']}")
        print(f"report: {output_path}")
    elif args.command == "compare-fixed-inputs":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        comparison = compare_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_fixed_input_comparison_markdown(comparison), encoding="utf-8")
        json_path.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"expected_group_count: {comparison['expected_group_count']}")
        print(f"complete_group_count: {comparison['complete_group_count']}")
        print(f"coverage_ratio: {comparison['coverage_ratio']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "compare-preview-fixed-inputs":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        comparison = compare_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(
            render_preview_fixed_input_comparison_markdown(comparison), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"expected_group_count: {comparison['expected_group_count']}")
        print(f"preview_ready_count: {comparison['preview_ready_count']}")
        print(f"preview_coverage_ratio: {comparison['preview_coverage_ratio']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "recommend-preview-fixed-inputs":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        recommendation = recommend_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(
            render_preview_recommendation_markdown(recommendation), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(recommendation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"expected_group_count: {recommendation['expected_group_count']}")
        print(f"selected_candidate_count: {recommendation['selected_candidate_count']}")
        print(f"selected_coverage_ratio: {recommendation['selected_coverage_ratio']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "propose-preview-fixed-inputs":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        proposal = propose_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_preview_revision_plan_markdown(proposal), encoding="utf-8")
        json_path.write_text(
            json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"expected_group_count: {proposal['expected_group_count']}")
        print(f"selected_candidate_count: {proposal['selected_candidate_count']}")
        print(f"selected_coverage_ratio: {proposal['selected_coverage_ratio']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "preview-iteration-fixed-inputs":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        iteration = preview_iteration_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_preview_iteration_markdown(iteration), encoding="utf-8")
        json_path.write_text(
            json.dumps(iteration, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"expected_group_count: {iteration['expected_group_count']}")
        print(f"selected_candidate_count: {iteration['selected_candidate_count']}")
        print(f"iteration_status: {iteration['iteration_status']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "apply-preview-revision-fixed-inputs":
        root = Path(args.root)
        revision_plans = None
        if args.revision_plan_json:
            revision_plan_data = json.loads(Path(args.revision_plan_json).read_text(encoding="utf-8"))
            revision_plans = list(
                revision_plan_data.get("preview_revision_plans")
                or revision_plan_data.get("revision_plans")
                or []
            )
        loop = run_preview_revision_loop_fixed_input_set(
            root,
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
            revision_plans=revision_plans,
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(
            render_preview_revision_loop_markdown(loop), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"rerun_count: {loop['rerun_count']}")
        print(f"before_iteration_status: {loop['before_iteration']['iteration_status']}")
        print(f"after_iteration_status: {loop['after_iteration']['iteration_status']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "summarize-preview-revision-loops":
        packet_paths = [Path(path) for path in args.packet_json]
        packets = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in packet_paths
        ]
        summary = summarize_preview_revision_loops(packets)
        output_path = packet_paths[0].parent / args.output
        json_path = packet_paths[0].parent / args.json_output
        output_path.write_text(
            render_preview_revision_loop_summary_markdown(summary), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"packet_count: {summary['packet_count']}")
        print(f"stable_design_principles: {summary['stable_design_principles']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "propose-stable-writer-profiles":
        summary_path = Path(args.summary_json)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        bundle = propose_stable_writer_profile_candidates(
            summary,
            base_profile_id=args.base_profile_id,
        )
        output_path = summary_path.parent / args.output
        json_path = summary_path.parent / args.json_output
        output_path.write_text(
            render_stable_writer_profile_candidates_markdown(bundle), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"candidate_count: {len(bundle['candidates'])}")
        print(f"base_profile_id: {bundle['base_profile_id']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "evaluate-stable-writer-profiles":
        summary_path = Path(args.summary_json)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        root = Path(args.root)
        packet = evaluate_stable_writer_profile_candidates(
            root,
            summary,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            base_profile_id=args.base_profile_id,
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        output_path = summary_path.parent / args.output
        json_path = summary_path.parent / args.json_output
        output_path.write_text(
            render_stable_writer_profile_evaluation_markdown(packet), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"candidate_count: {packet['candidate_count']}")
        print(f"selected_profile_count: {packet['selected_profile_count']}")
        print(f"selected_profile_ids: {packet['selected_profile_ids']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "evaluate-data-driven-writer-prior":
        root = Path(args.root)
        packet = evaluate_data_driven_writer_prior_fixed_input_set(
            root,
            samples_jsonl=Path(args.samples_jsonl),
            base_profile_id=args.base_profile_id,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        output_path = root / args.output
        json_path = root / args.json_output
        output_path.write_text(
            render_data_driven_writer_prior_evaluation_markdown(packet), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"selected: {packet['selected']}")
        print(f"selected_profile_id: {packet['selected_profile_id']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "offline-review":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        review = build_offline_review(registry.load_all())
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_offline_review_markdown(review), encoding="utf-8")
        json_path.write_text(
            json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"record_count: {review['record_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-review-packet":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        packet = build_human_review_packet(
            registry.load_all(),
            target_count=args.target_count,
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_human_review_packet_markdown(packet), encoding="utf-8")
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"record_count: {packet['record_count']}")
        print(f"representative_count: {packet['representative_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-feedback-loop":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        responses_data = None
        if args.responses_json:
            responses_data = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        loop = build_human_feedback_loop(
            registry.load_all(),
            responses_data=responses_data,
            reviewer_id=args.reviewer_id,
            target_count=args.target_count,
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        brief = build_human_review_revision_brief(
            loop["response_summary"]
            or {
                "note_count": 0,
                "reason_tag_counts": {},
                "note_examples": [],
            }
        )
        brief_md_path = root / args.brief_output
        brief_json_path = root / args.brief_json_output
        markdown_path.write_text(render_human_feedback_loop_markdown(loop), encoding="utf-8")
        json_path.write_text(
            json.dumps(loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        brief_md_path.write_text(render_human_review_revision_brief_markdown(brief), encoding="utf-8")
        brief_json_path.write_text(
            json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        plan = build_human_review_revision_plan(brief)
        plan_md_path = root / "human_review_revision_plan.md"
        plan_json_path = root / "human_review_revision_plan.json"
        plan_md_path.write_text(render_human_review_revision_plan_markdown(plan), encoding="utf-8")
        plan_json_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.brief_only:
            print(f"brief_status: {brief['brief_status']}")
            print(f"note_count: {brief['note_count']}")
            print(f"brief_report: {brief_md_path}")
            print(f"brief_json: {brief_json_path}")
            print(f"plan_status: {plan['plan_status']}")
            print(f"plan_report: {plan_md_path}")
            print(f"plan_json: {plan_json_path}")
        else:
            print(f"loop_status: {loop['loop_status']}")
            print(f"representative_count: {loop['packet']['representative_count']}")
            print(f"next_actions: {len(loop['next_actions'])}")
            print(f"report: {markdown_path}")
            print(f"json: {json_path}")
            print(f"brief_report: {brief_md_path}")
            print(f"brief_json: {brief_json_path}")
            print(f"plan_report: {plan_md_path}")
            print(f"plan_json: {plan_json_path}")
    elif args.command == "human-feedback-ui":
        from evaluation_harness.human_feedback_qt import launch_human_feedback_ui

        root = Path(args.root) if args.root else None
        packet_json = Path(args.packet_json) if args.packet_json else None
        responses_json = Path(args.responses_json) if args.responses_json else None
        summary_json = Path(args.summary_json) if args.summary_json else None
        brief_json = Path(args.brief_json) if args.brief_json else None
        brief_markdown = Path(args.brief_markdown) if args.brief_markdown else None
        plan_json = Path(args.plan_json) if args.plan_json else None
        plan_markdown = Path(args.plan_markdown) if args.plan_markdown else None
        preview_run_json = Path(args.preview_run_json) if args.preview_run_json else None
        preview_run_markdown = Path(args.preview_run_markdown) if args.preview_run_markdown else None
        launch_human_feedback_ui(
            root=root,
            packet_json=packet_json,
            responses_json=responses_json,
            summary_json=summary_json,
            brief_json=brief_json,
            brief_markdown=brief_markdown,
            plan_json=plan_json,
            plan_markdown=plan_markdown,
            preview_run_json=preview_run_json,
            preview_run_markdown=preview_run_markdown,
            reviewer_id=args.reviewer_id,
            target_count=args.target_count,
        )
    elif args.command == "human-feedback-revision-plan":
        if args.loop_json:
            loop = json.loads(Path(args.loop_json).read_text(encoding="utf-8"))
            brief = loop.get("revision_brief")
            if brief is None:
                brief = build_human_review_revision_brief(
                    loop.get(
                        "response_summary",
                        {"note_count": 0, "reason_tag_counts": {}, "note_examples": []},
                    )
                )
        elif args.brief_json:
            brief = json.loads(Path(args.brief_json).read_text(encoding="utf-8"))
        else:
            raise ValueError("--brief-json or --loop-json is required")
        plan = build_human_review_revision_plan(brief)
        if args.loop_json:
            base_dir = Path(args.loop_json).parent
        else:
            base_dir = Path(args.brief_json).parent
        output_path = _resolve_output_path(base_dir, args.output)
        json_path = _resolve_output_path(base_dir, args.json_output)
        output_path.write_text(render_human_review_revision_plan_markdown(plan), encoding="utf-8")
        json_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"plan_status: {plan['plan_status']}")
        print(f"dominant_focus_area: {plan['dominant_focus_area']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "human-feedback-preview-revision-plan":
        root = Path(args.root)
        if args.loop_json:
            loop = json.loads(Path(args.loop_json).read_text(encoding="utf-8"))
            brief = loop.get("revision_brief")
            if brief is None:
                brief = build_human_review_revision_brief(
                    loop.get(
                        "response_summary",
                        {"note_count": 0, "reason_tag_counts": {}, "note_examples": []},
                    )
                )
        elif args.brief_json:
            brief = json.loads(Path(args.brief_json).read_text(encoding="utf-8"))
        else:
            raise ValueError("--brief-json or --loop-json is required")
        registry = ExperimentRegistry(root / "registry.jsonl")
        preview_proposal = propose_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        combined = build_human_review_preview_revision_plan(brief, preview_proposal)
        output_path = _resolve_output_path(root, args.output)
        json_path = _resolve_output_path(root, args.json_output)
        output_path.write_text(
            render_human_review_preview_revision_plan_markdown(combined), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(combined, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"plan_status: {combined['plan_status']}")
        print(f"human_focus_area: {combined['human_focus_area']}")
        print(f"preview_selected_candidate_count: {combined['preview_selected_candidate_count']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "human-feedback-preview-revision-run":
        root = Path(args.root)
        focus_areas = {item for item in _parse_csv(args.focus_areas)}
        if args.loop_json:
            loop = json.loads(Path(args.loop_json).read_text(encoding="utf-8"))
            brief = loop.get("revision_brief")
            if brief is None:
                brief = build_human_review_revision_brief(
                    loop.get(
                        "response_summary",
                        {"note_count": 0, "reason_tag_counts": {}, "note_examples": []},
                    )
                )
        elif args.brief_json:
            brief = json.loads(Path(args.brief_json).read_text(encoding="utf-8"))
        else:
            raise ValueError("--brief-json or --loop-json is required")
        registry = ExperimentRegistry(root / "registry.jsonl")
        preview_proposal = propose_preview_fixed_input_set(
            registry.load_all(),
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
        )
        combined = build_human_review_preview_revision_plan(brief, preview_proposal)
        preview_revision_plans = list(combined.get("preview_revision_plans", []))
        if focus_areas:
            preview_revision_plans = [
                plan for plan in preview_revision_plans if plan.get("focus_area") in focus_areas
            ]
        if args.max_items > 0:
            preview_revision_plans = preview_revision_plans[: args.max_items]
        run = run_preview_revision_loop_fixed_input_set(
            root,
            expected_input_texts=tuple(get_evaluation_inputs(args.input_set)),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
            baseline_generator=args.baseline_generator,
            revision_plans=preview_revision_plans,
        )
        output_path = _resolve_output_path(root, args.output)
        json_path = _resolve_output_path(root, args.json_output)
        output_path.write_text(
            render_preview_revision_loop_markdown(run), encoding="utf-8"
        )
        json_path.write_text(
            json.dumps(
                {
                    "human_revision_plan": combined,
                    "preview_revision_run": run,
                    "rerun_plan_count": len(preview_revision_plans),
                    "focus_areas": sorted(focus_areas),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"human_focus_area: {combined['human_focus_area']}")
        print(f"preview_selected_candidate_count: {combined['preview_selected_candidate_count']}")
        print(f"rerun_plan_count: {len(preview_revision_plans)}")
        print(f"rerun_count: {run['rerun_count']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "preview-review-packet":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        packet = build_human_review_packet(
            registry.load_all(),
            target_count=args.target_count,
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_human_review_packet_markdown(packet), encoding="utf-8")
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"record_count: {packet['record_count']}")
        print(f"representative_count: {packet['representative_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-abx-packet":
        focus_areas = tuple(_parse_csv(args.focus_areas))
        if args.recommendation_json:
            recommendation_path = Path(args.recommendation_json)
            recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
            packet = build_human_abx_packet(
                recommendation=recommendation,
                focus_areas=focus_areas,
                max_items=args.max_items or None,
            )
            base_dir = recommendation_path.parent
        else:
            if not args.root:
                raise ValueError("--root is required when --recommendation-json is not set")
            root = Path(args.root)
            registry = ExperimentRegistry(root / "registry.jsonl")
            packet = build_human_abx_packet(
                registry.load_all(),
                expected_input_texts=get_evaluation_inputs(args.input_set),
                expected_seeds=tuple(_parse_seeds(args.seeds)),
                baseline_generator=args.baseline_generator,
                focus_areas=focus_areas,
                max_items=args.max_items or None,
            )
            base_dir = root
        markdown_path = _resolve_output_path(base_dir, args.output)
        json_path = _resolve_output_path(base_dir, args.json_output)
        markdown_path.write_text(render_human_abx_packet_markdown(packet), encoding="utf-8")
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"record_count: {packet['record_count']}")
        print(f"selected_candidate_count: {packet['selected_candidate_count']}")
        print(f"selected_profile_counts: {packet['selected_profile_counts']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-abx-feedback-loop":
        focus_areas = tuple(_parse_csv(args.focus_areas))
        if args.recommendation_json:
            recommendation = json.loads(Path(args.recommendation_json).read_text(encoding="utf-8"))
            packet = build_human_abx_packet(
                recommendation=recommendation,
                focus_areas=focus_areas,
                max_items=args.max_items or None,
            )
            packet_path = Path(args.recommendation_json)
        else:
            packet = json.loads(Path(args.packet_json).read_text(encoding="utf-8"))
            packet_path = Path(args.packet_json)
        responses_data = None
        if args.responses_json:
            responses_data = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        loop = build_human_abx_feedback_loop(
            packet,
            responses_data=responses_data,
            evaluator_id=args.evaluator_id,
            max_items=args.max_items,
        )
        output_path = _resolve_output_path(packet_path.parent, args.output)
        json_path = _resolve_output_path(packet_path.parent, args.json_output)
        template_json_path = _resolve_output_path(packet_path.parent, args.template_json_output)
        output_path.write_text(render_abx_feedback_loop_markdown(loop), encoding="utf-8")
        json_path.write_text(
            json.dumps(loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        template_json_path.write_text(
            json.dumps(loop["response_template"], ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"loop_status: {loop['loop_status']}")
        print(f"next_actions: {len(loop['next_actions'])}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
        print(f"template_json: {template_json_path}")
    elif args.command == "human-abx-bundle":
        focus_areas = tuple(_parse_csv(args.focus_areas))
        if args.recommendation_json:
            recommendation_path = Path(args.recommendation_json)
            packet = build_human_abx_packet(
                recommendation=json.loads(recommendation_path.read_text(encoding="utf-8")),
                focus_areas=focus_areas,
                max_items=args.max_items or None,
            )
            base_dir = recommendation_path.parent
        else:
            if not args.root:
                raise ValueError("--root is required when --recommendation-json is not set")
            root = Path(args.root)
            packet = build_human_abx_packet(
                ExperimentRegistry(root / "registry.jsonl").load_all(),
                expected_input_texts=get_evaluation_inputs(args.input_set),
                expected_seeds=tuple(_parse_seeds(args.seeds)),
                baseline_generator=args.baseline_generator,
                focus_areas=focus_areas,
                max_items=args.max_items or None,
            )
            base_dir = root
        responses_data = _load_json_if_present(args.responses_json)
        workbook = build_abx_workbook(
            packet,
            responses_data=responses_data,
            evaluator_id=args.evaluator_id,
            max_items=args.max_items,
        )
        feedback_loop = build_human_abx_feedback_loop(
            packet,
            responses_data=responses_data,
            evaluator_id=args.evaluator_id,
            max_items=args.max_items,
        )
        bundle_dir = _resolve_output_path(base_dir, args.output_dir) if args.output_dir else base_dir
        bundle_dir.mkdir(parents=True, exist_ok=True)
        prefix = args.output_prefix or _default_abx_bundle_prefix(focus_areas)
        packet_md_path = bundle_dir / f"{prefix}_packet.md"
        packet_json_path = bundle_dir / f"{prefix}_packet.json"
        workbook_md_path = bundle_dir / f"{prefix}_workbook.md"
        workbook_json_path = bundle_dir / f"{prefix}_workbook.json"
        feedback_md_path = bundle_dir / f"{prefix}_feedback_loop.md"
        feedback_json_path = bundle_dir / f"{prefix}_feedback_loop.json"
        template_json_path = bundle_dir / f"{prefix}_response_template.json"
        responses_json_path = bundle_dir / f"{prefix}_responses.json"
        packet_md_path.write_text(render_human_abx_packet_markdown(packet), encoding="utf-8")
        packet_json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        workbook_md_path.write_text(render_abx_workbook_markdown(workbook), encoding="utf-8")
        workbook_json_path.write_text(
            json.dumps(workbook, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        feedback_md_path.write_text(render_abx_feedback_loop_markdown(feedback_loop), encoding="utf-8")
        feedback_json_path.write_text(
            json.dumps(feedback_loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        template_json_path.write_text(
            json.dumps(feedback_loop["response_template"], ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        responses_json_path.write_text(
            json.dumps(build_abx_responses_from_workbook(workbook), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"packet_items: {len(packet['abx_items'])}")
        print(f"workbook_rows: {len(workbook['rows'])}")
        print(f"feedback_status: {feedback_loop['loop_status']}")
        print(f"bundle_dir: {bundle_dir}")
        print(f"bundle_prefix: {prefix}")
    elif args.command == "human-abx-bundle-followup":
        bundle_dir = Path(args.bundle_dir)
        packet_path = _find_bundle_artifact_path(bundle_dir, args.bundle_prefix, "packet.json")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        workbook_path = (
            Path(args.workbook_json)
            if args.workbook_json
            else _find_bundle_artifact_path(bundle_dir, args.bundle_prefix, "workbook.json")
        )
        responses_path = Path(args.responses_json) if args.responses_json else None
        workbook = None
        if workbook_path.exists():
            workbook = json.loads(workbook_path.read_text(encoding="utf-8"))
        if workbook is not None and args.workbook_json:
            responses_data = build_abx_responses_from_workbook(workbook)
        elif responses_path is not None:
            responses_data = json.loads(responses_path.read_text(encoding="utf-8"))
        else:
            if workbook is None:
                workbook = json.loads((bundle_dir / f"{args.bundle_prefix}_workbook.json").read_text(encoding="utf-8"))
            responses_data = build_abx_responses_from_workbook(workbook)
        responses = load_abx_responses(responses_data)
        packet_items = {
            str(item.get("item_id", "")): item for item in packet.get("abx_items", [])
        }
        response_summary = summarize_abx_responses(
            responses,
            items=[
                _abx_item_from_packet(packet_items[item_id])
                for item_id in sorted({response.item_id for response in responses})
                if item_id in packet_items
            ],
        )
        feedback_loop = build_human_abx_feedback_loop(
            packet,
            responses_data=responses_data,
            evaluator_id=args.evaluator_id,
            max_items=args.max_items,
        )
        plan = build_abx_revision_plan(feedback_loop)
        run = run_abx_revision_loop(Path(args.root), feedback_loop=feedback_loop)
        output_prefix = args.output_prefix or f"{args.bundle_prefix}_followup"
        summary_md_path = bundle_dir / f"{output_prefix}_response_summary.md"
        summary_json_path = bundle_dir / f"{output_prefix}_response_summary.json"
        responses_json_path = bundle_dir / f"{output_prefix}_responses.json"
        pending_packet_md_path = bundle_dir / f"{output_prefix}_pending_packet.md"
        pending_packet_json_path = bundle_dir / f"{output_prefix}_pending_packet.json"
        pending_workbook_md_path = bundle_dir / f"{output_prefix}_pending_workbook.md"
        pending_workbook_json_path = bundle_dir / f"{output_prefix}_pending_workbook.json"
        feedback_md_path = bundle_dir / f"{output_prefix}_feedback_loop.md"
        feedback_json_path = bundle_dir / f"{output_prefix}_feedback_loop.json"
        plan_md_path = bundle_dir / f"{output_prefix}_revision_plan.md"
        plan_json_path = bundle_dir / f"{output_prefix}_revision_plan.json"
        run_md_path = bundle_dir / f"{output_prefix}_revision_run.md"
        run_json_path = bundle_dir / f"{output_prefix}_revision_run.json"
        summary_md_path.write_text(render_abx_summary_markdown(response_summary), encoding="utf-8")
        summary_json_path.write_text(
            json.dumps(response_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        responses_json_path.write_text(
            json.dumps(responses_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if workbook is not None:
            completed_row_count, pending_row_count, completion_ratio = summarize_abx_workbook_completion(workbook)
            print(f"completed_row_count: {completed_row_count}")
            print(f"pending_row_count: {pending_row_count}")
            print(f"completion_ratio: {completion_ratio}")
            if args.pending_only:
                pending_rows = [
                    row
                    for row in workbook.get("rows", [])
                    if not str(row.get("choice", "")).strip() or not str(row.get("confidence", "")).strip()
                ]
                pending_packet = build_abx_pending_packet(packet, workbook)
                pending_workbook = {
                    **workbook,
                    "loop_status": workbook.get("loop_status", feedback_loop["loop_status"]),
                    "next_actions": workbook.get("next_actions", feedback_loop["next_actions"]),
                    "response_template": workbook.get("response_template", feedback_loop["response_template"]),
                    "packet": workbook.get("packet", feedback_loop["packet"]),
                    "rows": pending_rows,
                }
                pending_packet_md_path.write_text(
                    render_human_abx_packet_markdown(pending_packet), encoding="utf-8"
                )
                pending_packet_json_path.write_text(
                    json.dumps(pending_packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                pending_workbook_md_path.write_text(
                    render_abx_workbook_markdown(pending_workbook), encoding="utf-8"
                )
                pending_workbook_json_path.write_text(
                    json.dumps(pending_workbook, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(f"pending_packet_rows: {len(pending_packet['abx_items'])}")
                print(f"pending_workbook_rows: {len(pending_rows)}")
                if args.next_bundle_dir or args.chain_next_bundle:
                    if args.next_bundle_dir:
                        next_bundle_dir = _resolve_output_path(bundle_dir, args.next_bundle_dir)
                    else:
                        next_bundle_dir = bundle_dir.parent / _increment_bundle_name(bundle_dir.name)
                    next_bundle_dir.mkdir(parents=True, exist_ok=True)
                    next_prefix = args.next_bundle_prefix or (
                        _increment_bundle_name(args.bundle_prefix) if args.chain_next_bundle else f"{output_prefix}_next"
                    )
                    next_workbook = build_abx_workbook(
                        pending_packet,
                        evaluator_id=args.evaluator_id,
                        max_items=args.max_items,
                    )
                    next_feedback_loop = build_human_abx_feedback_loop(
                        pending_packet,
                        evaluator_id=args.evaluator_id,
                        max_items=args.max_items,
                    )
                    next_packet_md_path = next_bundle_dir / f"{next_prefix}_packet.md"
                    next_packet_json_path = next_bundle_dir / f"{next_prefix}_packet.json"
                    next_workbook_md_path = next_bundle_dir / f"{next_prefix}_workbook.md"
                    next_workbook_json_path = next_bundle_dir / f"{next_prefix}_workbook.json"
                    next_feedback_md_path = next_bundle_dir / f"{next_prefix}_feedback_loop.md"
                    next_feedback_json_path = next_bundle_dir / f"{next_prefix}_feedback_loop.json"
                    next_template_json_path = next_bundle_dir / f"{next_prefix}_response_template.json"
                    next_responses_json_path = next_bundle_dir / f"{next_prefix}_responses.json"
                    next_packet_md_path.write_text(
                        render_human_abx_packet_markdown(pending_packet), encoding="utf-8"
                    )
                    next_packet_json_path.write_text(
                        json.dumps(pending_packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    next_workbook_md_path.write_text(
                        render_abx_workbook_markdown(next_workbook), encoding="utf-8"
                    )
                    next_workbook_json_path.write_text(
                        json.dumps(next_workbook, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    next_feedback_md_path.write_text(
                        render_abx_feedback_loop_markdown(next_feedback_loop), encoding="utf-8"
                    )
                    next_feedback_json_path.write_text(
                        json.dumps(next_feedback_loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    next_template_json_path.write_text(
                        json.dumps(
                            next_feedback_loop["response_template"],
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    next_responses_json_path.write_text(
                        json.dumps(build_abx_responses_from_workbook(next_workbook), ensure_ascii=False, indent=2, sort_keys=True)
                        + "\n",
                        encoding="utf-8",
                    )
                    print(f"next_bundle_dir: {next_bundle_dir}")
                    print(f"next_bundle_prefix: {next_prefix}")
        feedback_md_path.write_text(render_abx_feedback_loop_markdown(feedback_loop), encoding="utf-8")
        feedback_json_path.write_text(
            json.dumps(feedback_loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        plan_md_path.write_text(render_abx_revision_plan_markdown(plan), encoding="utf-8")
        plan_json_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        run_md_path.write_text(render_abx_revision_run_markdown(run), encoding="utf-8")
        run_json_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"response_count: {response_summary['response_count']}")
        print(f"selected_item_count: {plan['selected_item_count']}")
        print(f"rerun_count: {run['rerun_count']}")
        print(f"preview_changed_count: {run['preview_changed_count']}")
        print(f"report: {run_md_path}")
        print(f"json: {run_json_path}")
        print(f"responses_json: {responses_json_path}")
    elif args.command == "human-abx-bundle-chain-status":
        bundle_status = _summarize_abx_bundle_chain(
            Path(args.bundle_dir),
            args.bundle_prefix,
            max_depth=args.max_depth,
        )
        bundle_dir = Path(args.bundle_dir)
        markdown_path = bundle_dir / args.output
        json_path = bundle_dir / args.json_output
        markdown_path.write_text(render_abx_bundle_chain_status_markdown(bundle_status), encoding="utf-8")
        json_path.write_text(
            json.dumps(bundle_status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"bundle_count: {bundle_status['bundle_count']}")
        print(f"open_bundle_count: {bundle_status['open_bundle_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-abx-bundle-sweep-status":
        sweep_status = _summarize_abx_bundle_sweep(Path(args.root), max_depth=args.max_depth)
        root = Path(args.root)
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_abx_bundle_sweep_status_markdown(sweep_status), encoding="utf-8")
        json_path.write_text(
            json.dumps(sweep_status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"bundle_root_count: {sweep_status['bundle_root_count']}")
        print(f"open_bundle_root_count: {sweep_status['open_bundle_root_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "abx-workbook":
        packet = _load_abx_packet_from_args(args)
        responses_data = None
        if args.responses_json:
            responses_data = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        workbook = build_abx_workbook(
            packet,
            responses_data=responses_data,
            evaluator_id=args.evaluator_id,
            max_items=args.max_items,
        )
        packet_path = Path(args.recommendation_json or args.packet_json)
        output_path = _resolve_output_path(packet_path.parent, args.output)
        json_path = _resolve_output_path(packet_path.parent, args.json_output)
        output_path.write_text(render_abx_workbook_markdown(workbook), encoding="utf-8")
        json_path.write_text(
            json.dumps(workbook, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        responses_path = _resolve_output_path(packet_path.parent, args.responses_output)
        responses_path.write_text(
            json.dumps(build_abx_responses_from_workbook(workbook), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"loop_status: {workbook['loop_status']}")
        print(f"row_count: {len(workbook['rows'])}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
        print(f"responses_json: {responses_path}")
    elif args.command == "validate-human-review":
        packet_path = Path(args.packet_json)
        responses_path = Path(args.responses_json)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        responses = load_human_review_responses(
            json.loads(responses_path.read_text(encoding="utf-8"))
        )
        summary = summarize_human_review_responses(packet, responses)
        output_path = responses_path.parent / args.output
        json_path = responses_path.parent / args.json_output
        output_path.write_text(render_human_review_response_markdown(summary), encoding="utf-8")
        json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"response_count: {summary['response_count']}")
        print(f"can_proceed_to_plot: {summary['can_proceed_to_plot']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "validate-abx-responses":
        packet_path = Path(args.packet_json)
        responses_path = Path(args.responses_json)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        responses = load_abx_responses(json.loads(responses_path.read_text(encoding="utf-8")))
        packet_items = {
            str(item.get("item_id", "")): item for item in packet.get("abx_items", [])
        }
        summary = summarize_abx_responses(
            responses,
            items=[
                _abx_item_from_packet(packet_items[item_id])
                for item_id in sorted({response.item_id for response in responses})
                if item_id in packet_items
            ],
        )
        output_path = _resolve_output_path(responses_path.parent, args.output)
        json_path = _resolve_output_path(responses_path.parent, args.json_output)
        output_path.write_text(render_abx_summary_markdown(summary), encoding="utf-8")
        json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"response_count: {summary['response_count']}")
        print(f"tie_rate: {summary['tie_rate']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "abx-revision-plan":
        if args.feedback_loop_json:
            feedback_loop = json.loads(Path(args.feedback_loop_json).read_text(encoding="utf-8"))
        else:
            packet = _load_abx_packet_from_args(args)
            responses_data = _load_json_if_present(args.responses_json)
            feedback_loop = build_human_abx_feedback_loop(
                packet,
                responses_data=responses_data,
                evaluator_id=args.evaluator_id,
                max_items=args.max_items,
            )
        plan = build_abx_revision_plan(feedback_loop)
        output_path = _resolve_output_path(Path(args.feedback_loop_json).parent, args.output)
        json_path = _resolve_output_path(Path(args.feedback_loop_json).parent, args.json_output)
        if not args.feedback_loop_json:
            base_dir = Path(args.packet_json).parent
            output_path = _resolve_output_path(base_dir, args.output)
            json_path = _resolve_output_path(base_dir, args.json_output)
        output_path.write_text(render_abx_revision_plan_markdown(plan), encoding="utf-8")
        json_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"response_count: {plan['response_count']}")
        print(f"selected_item_count: {plan['selected_item_count']}")
        print(f"report: {output_path}")
        print(f"json: {json_path}")
    elif args.command == "abx-revision-run":
        root = Path(args.root)
        if args.feedback_loop_json:
            feedback_loop = json.loads(Path(args.feedback_loop_json).read_text(encoding="utf-8"))
        else:
            packet = _load_abx_packet_from_args(args)
            responses_data = _load_json_if_present(args.responses_json)
            feedback_loop = build_human_abx_feedback_loop(
                packet,
                responses_data=responses_data,
                evaluator_id=args.evaluator_id,
                max_items=args.max_items,
            )
        run = run_abx_revision_loop(root, feedback_loop=feedback_loop)
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_abx_revision_run_markdown(run), encoding="utf-8")
        json_path.write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"rerun_count: {run['rerun_count']}")
        print(f"before_record_count: {run['before_record_count']}")
        print(f"after_record_count: {run['after_record_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "plot-ready-packet":
        root = Path(args.root)
        human_summary_path = Path(args.human_summary_json)
        registry = ExperimentRegistry(root / "registry.jsonl")
        human_summary = json.loads(human_summary_path.read_text(encoding="utf-8"))
        packet = build_plot_ready_packet(registry.load_all(), human_summary)
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_plot_ready_packet_markdown(packet), encoding="utf-8")
        json_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"plot_ready_count: {packet['plot_ready_count']}")
        print(f"safety_ok_count: {packet['safety_ok_count']}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "self-check":
        root = Path(args.root)
        result = run_self_check(root, seed=args.seed)
        run_root = Path(result.run_root)
        markdown_path = run_root / args.output
        json_path = run_root / args.json_output
        markdown_path.write_text(render_self_check_markdown(result), encoding="utf-8")
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"status: {result.status}")
        print(f"run_root: {run_root}")
        print(f"registry_record_count: {result.registry_record_count}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "goal-audit":
        root = Path(args.root)
        result = run_goal_audit(root, seed=args.seed)
        markdown_path = Path(result.root) / args.output
        json_path = Path(result.root) / args.json_output
        markdown_path.write_text(render_goal_audit_markdown(result), encoding="utf-8")
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"status: {result.status}")
        print(f"root: {result.root}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "attach-scan":
        root = Path(args.root)
        metadata = ScanMetadata.from_dict(
            json.loads(Path(args.metadata_json).read_text(encoding="utf-8"))
        )
        attach_scan_artifact(
            registry=ExperimentRegistry(root / "registry.jsonl"),
            artifacts=ArtifactStore(root / "artifacts"),
            experiment_id=args.experiment_id,
            scan_path=args.scan_path,
            metadata=metadata,
        )
        print(f"attached scan: {args.experiment_id}")
    elif args.command == "structure-uniform":
        record = run_structure_uniform(
            root=Path(args.root),
            experiment_id=args.experiment_id,
            input_text=args.input_text,
            seed=args.seed,
            profile_id=args.profile_id,
            config=StructureUniformConfig(),
        )
        print(f"registered {record.experiment_id}")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"report: {record.artifacts['report']}")
    elif args.command == "structure-uniform-batch":
        records = run_structure_uniform_batch(
            root=Path(args.root),
            input_texts=_structure_inputs(args.input_set),
            seeds=_parse_seeds(args.seeds),
            profile_id=args.profile_id,
            experiment_prefix=args.experiment_prefix,
            config=StructureUniformConfig(),
        )
        print(f"registered {len(records)} experiments")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"summary: {Path(args.root) / 'structure_summary.md'}")
    elif args.command == "structure-motion":
        record = run_structure_motion(
            root=Path(args.root),
            experiment_id=args.experiment_id,
            input_text=args.input_text,
            seed=args.seed,
            profile_id=args.profile_id,
            config=StructureMotionConfig(
                shape_variation=args.shape_variation,
                layout_variation=args.layout_variation,
            ),
        )
        print(f"registered {record.experiment_id}")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"report: {record.artifacts['report']}")
    elif args.command == "structure-motion-batch":
        records = run_structure_motion_batch(
            root=Path(args.root),
            input_texts=_structure_inputs(args.input_set),
            seeds=_parse_seeds(args.seeds),
            profile_id=args.profile_id,
            experiment_prefix=args.experiment_prefix,
            config=StructureMotionConfig(
                shape_variation=args.shape_variation,
                layout_variation=args.layout_variation,
            ),
        )
        print(f"registered {len(records)} experiments")
        print(f"registry: {Path(args.root) / 'registry.jsonl'}")
        print(f"summary: {Path(args.root) / 'motion_summary.md'}")


def run_smoke(root: Path, experiment_id: str, input_text: str) -> None:
    registry = ExperimentRegistry(root / "registry.jsonl")
    artifacts = ArtifactStore(root / "artifacts")

    trajectory = [
        {"x": 0.0, "y": 0.0, "t": 0, "pen_state": 0, "pressure": 0.0},
        {"x": 1.0, "y": 1.0, "t": 20, "pen_state": 1, "pressure": 0.5},
        {"x": 2.0, "y": 1.2, "t": 40, "pen_state": 1, "pressure": 0.6},
        {"x": 2.5, "y": 1.3, "t": 60, "pen_state": 0, "pressure": 0.0},
    ]
    trajectory_path = artifacts.write_json(experiment_id, "trajectory.json", trajectory)
    metrics = compute_trajectory_metrics(trajectory)
    record = ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="registry smoke test records artifacts and metrics",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=1,
        generator="smoke-generator",
        exporter="none",
        artifacts={"trajectory": trajectory_path},
        metrics=metrics,
        failure_tags=[],
        next_action="replace smoke trajectory with baseline generator output",
    )
    report_path = artifacts.write_text(experiment_id, "report.md", render_markdown_report(record))
    record = ExperimentRecord(
        **{
            **record.to_dict(),
            "artifacts": {**record.artifacts, "report": report_path},
        }
    )
    registry.append(record)
    print(f"registered {experiment_id}")
    print(f"registry: {registry.path}")
    print(f"report: {report_path}")


def _parse_seeds(raw: str) -> list[int]:
    seeds = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not seeds:
        raise ValueError("at least one seed is required")
    if any(seed < 0 for seed in seeds):
        raise ValueError("seeds must be non-negative")
    return seeds


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _load_json_if_present(path: str) -> dict[str, object] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_output_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute() or path.parent != Path("."):
        return path
    return base_dir / path


def _default_abx_bundle_prefix(focus_areas: tuple[str, ...]) -> str:
    if not focus_areas:
        return "abx_bundle"
    return "_".join(sorted(focus_areas)) + "_abx"


def _find_bundle_artifact_path(bundle_dir: Path, bundle_prefix: str, suffix: str) -> Path:
    candidates = [bundle_prefix]
    version_match = re.match(r"^(.*)_v\d+$", bundle_prefix)
    if version_match:
        candidates.append(version_match.group(1))
    for candidate in candidates:
        path = bundle_dir / f"{candidate}_{suffix}"
        if path.exists():
            return path
    return bundle_dir / f"{bundle_prefix}_{suffix}"


def _increment_bundle_name(name: str) -> str:
    match = re.match(r"^(.*?)(?:_v(\d+))?$", name)
    if not match:
        return f"{name}_v2"
    base, version = match.groups()
    if version is None:
        return f"{name}_v2"
    return f"{base}_v{int(version) + 1}"


def _markdown_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _load_abx_packet_from_args(args: argparse.Namespace) -> dict[str, object]:
    focus_areas = tuple(_parse_csv(getattr(args, "focus_areas", "")))
    if getattr(args, "recommendation_json", ""):
        recommendation = json.loads(Path(args.recommendation_json).read_text(encoding="utf-8"))
        return build_human_abx_packet(
            recommendation=recommendation,
            focus_areas=focus_areas,
            max_items=getattr(args, "max_items", None) or None,
        )
    if not getattr(args, "packet_json", ""):
        raise ValueError("--packet-json or --recommendation-json is required")
    return json.loads(Path(args.packet_json).read_text(encoding="utf-8"))


def _abx_item_from_packet(item: dict[str, object]) -> AbxItem:
    return AbxItem(
        item_id=str(item.get("item_id", "")),
        prompt=str(item.get("prompt", "")),
        option_a_artifact=str(item.get("option_a_artifact", "")),
        option_b_artifact=str(item.get("option_b_artifact", "")),
        question=str(item.get("question", "")),
        expected_preference=item.get("expected_preference"),
    )


def _summarize_abx_bundle_chain(
    bundle_dir: Path,
    bundle_prefix: str,
    *,
    max_depth: int,
) -> dict[str, object]:
    bundles: list[dict[str, object]] = []
    current_dir = bundle_dir
    current_prefix = bundle_prefix
    for _ in range(max_depth if max_depth > 0 else 1):
        packet_path = _find_bundle_artifact_path(current_dir, current_prefix, "packet.json")
        if not packet_path.exists():
            break
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        workbook_path = _find_bundle_artifact_path(current_dir, current_prefix, "workbook.json")
        workbook = json.loads(workbook_path.read_text(encoding="utf-8")) if workbook_path.exists() else None
        packet_items = list(packet.get("abx_items", []))
        if workbook is not None:
            completed_row_count, pending_row_count, completion_ratio = summarize_abx_workbook_completion(workbook)
        else:
            completed_row_count, pending_row_count, completion_ratio = 0, len(packet_items), 0.0
        revision_run_path = _latest_bundle_artifact_path(current_dir, "*_revision_run.json")
        revision_run = (
            json.loads(revision_run_path.read_text(encoding="utf-8"))
            if revision_run_path is not None and revision_run_path.exists()
            else None
        )
        next_bundle_dir = current_dir.parent / _increment_bundle_name(current_dir.name)
        next_bundle_prefix = _increment_bundle_name(current_prefix)
        next_packet_path = _find_bundle_artifact_path(next_bundle_dir, next_bundle_prefix, "packet.json")
        next_bundle_exists = next_packet_path.exists()
        bundles.append(
            {
                "bundle_dir": str(current_dir),
                "bundle_prefix": current_prefix,
                "packet_item_count": len(packet_items),
                "workbook_row_count": len(workbook.get("rows", [])) if workbook is not None else 0,
                "completed_row_count": completed_row_count,
                "pending_row_count": pending_row_count,
                "completion_ratio": completion_ratio,
                "revision_rerun_count": int(revision_run.get("rerun_count", 0)) if revision_run else 0,
                "revision_preview_changed_count": int(revision_run.get("preview_changed_count", 0)) if revision_run else 0,
                "next_bundle_dir": str(next_bundle_dir),
                "next_bundle_prefix": next_bundle_prefix,
                "next_bundle_exists": next_bundle_exists,
            }
        )
        if not next_bundle_exists:
            break
        current_dir = next_bundle_dir
        current_prefix = next_bundle_prefix

    open_bundle_count = sum(1 for bundle in bundles if bundle["pending_row_count"])
    chain_status = "complete" if bundles and not bundles[-1]["next_bundle_exists"] and not bundles[-1]["pending_row_count"] else "active"
    return {
        "chain_status": chain_status,
        "bundle_count": len(bundles),
        "open_bundle_count": open_bundle_count,
        "bundles": bundles,
    }


def _summarize_abx_bundle_sweep(root: Path, *, max_depth: int) -> dict[str, object]:
    bundle_roots = sorted(
        {
            path
            for path in root.iterdir()
            if path.is_dir() and re.match(r"^.+_bundle_v1$", path.name)
        },
        key=lambda path: path.name,
    )
    bundle_chains = [
        _summarize_abx_bundle_chain(bundle_root, _bundle_prefix_from_dir(bundle_root), max_depth=max_depth)
        for bundle_root in bundle_roots
    ]
    ranked_bundle_chains = sorted(
        bundle_chains,
        key=lambda chain: (
            -sum(int(bundle.get("revision_preview_changed_count", 0)) for bundle in chain.get("bundles", [])),
            -sum(int(bundle.get("revision_rerun_count", 0)) for bundle in chain.get("bundles", [])),
            chain.get("bundles", [{}])[0].get("bundle_dir", "") if chain.get("bundles") else "",
        ),
    )
    return {
        "root": str(root),
        "bundle_root_count": len(bundle_chains),
        "open_bundle_root_count": sum(1 for chain in bundle_chains if chain["open_bundle_count"]),
        "bundle_chains": bundle_chains,
        "ranked_bundle_chains": ranked_bundle_chains,
    }


def _bundle_prefix_from_dir(bundle_dir: Path) -> str:
    packet_files = sorted(bundle_dir.glob("*_packet.json"))
    if not packet_files:
        return bundle_dir.name[:-3]
    preferred: list[Path] = []
    fallback: list[Path] = []
    for packet_path in packet_files:
        prefix = packet_path.name[: -len("_packet.json")]
        if "followup" in prefix or "pending" in prefix:
            fallback.append(packet_path)
        else:
            preferred.append(packet_path)
    selected = preferred or fallback or packet_files
    selected.sort(key=lambda path: (len(path.name), path.name))
    return selected[0].name[: -len("_packet.json")]


def _latest_bundle_artifact_path(bundle_dir: Path, pattern: str) -> Path | None:
    candidates = sorted(bundle_dir.glob(pattern))
    if not candidates:
        return None
    return candidates[-1]


def render_abx_bundle_chain_status_markdown(status: dict[str, object]) -> str:
    lines = [
        "# ABX Bundle Chain Status",
        "",
        f"- chain_status: `{status['chain_status']}`",
        f"- bundle_count: `{status['bundle_count']}`",
        f"- open_bundle_count: `{status['open_bundle_count']}`",
        "",
        "## Bundles",
        "",
    ]
    bundles = list(status.get("bundles", []))
    if not bundles:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| bundle_dir | bundle_prefix | packet_items | workbook_rows | completed | pending | completion_ratio | rerun_count | preview_changed_count | next_bundle_exists |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for bundle in bundles:
        lines.append(
            "| "
            f"{_markdown_cell(str(bundle['bundle_dir']))} | "
            f"{_markdown_cell(str(bundle['bundle_prefix']))} | "
            f"{_markdown_cell(str(bundle['packet_item_count']))} | "
            f"{_markdown_cell(str(bundle['workbook_row_count']))} | "
            f"{_markdown_cell(str(bundle['completed_row_count']))} | "
            f"{_markdown_cell(str(bundle['pending_row_count']))} | "
            f"{_markdown_cell(str(bundle['completion_ratio']))} | "
            f"{_markdown_cell(str(bundle['revision_rerun_count']))} | "
            f"{_markdown_cell(str(bundle['revision_preview_changed_count']))} | "
            f"{_markdown_cell(str(bundle['next_bundle_exists']))} |"
        )
    return "\n".join(lines) + "\n"


def render_abx_bundle_sweep_status_markdown(status: dict[str, object]) -> str:
    lines = [
        "# ABX Bundle Sweep Status",
        "",
        f"- root: `{status['root']}`",
        f"- bundle_root_count: `{status['bundle_root_count']}`",
        f"- open_bundle_root_count: `{status['open_bundle_root_count']}`",
        "",
        "## Bundle Chains",
        "",
    ]
    ranked_chains = list(status.get("ranked_bundle_chains", []))
    if ranked_chains:
        lines.extend(
            [
                "### Recommended Order",
                "",
            ]
        )
        for chain in ranked_chains:
            bundles = list(chain.get("bundles", []))
            if not bundles:
                continue
            last_bundle = bundles[-1]
            total_changed = sum(int(bundle.get("revision_preview_changed_count", 0)) for bundle in bundles)
            total_rerun = sum(int(bundle.get("revision_rerun_count", 0)) for bundle in bundles)
            lines.append(
                f"- `{bundles[0]['bundle_dir']}` / `{bundles[0]['bundle_prefix']}`: "
                f"changed=`{total_changed}` rerun=`{total_rerun}` latest=`{last_bundle.get('bundle_prefix', '')}`"
            )
        lines.append("")
    chains = list(status.get("bundle_chains", []))
    if not chains:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| bundle_dir | bundle_prefix | bundle_count | open_bundle_count | chain_status | latest_rerun_count | latest_preview_changed_count |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for chain in chains:
        bundles = list(chain.get("bundles", []))
        last_bundle = bundles[-1] if bundles else {}
        lines.append(
            "| "
            f"{_markdown_cell(str(bundles[0]['bundle_dir']) if bundles else '')} | "
            f"{_markdown_cell(str(bundles[0]['bundle_prefix']) if bundles else '')} | "
            f"{_markdown_cell(str(chain['bundle_count']))} | "
            f"{_markdown_cell(str(chain['open_bundle_count']))} | "
            f"{_markdown_cell(str(chain['chain_status']))} | "
            f"{_markdown_cell(str(last_bundle.get('revision_rerun_count', 0)) if last_bundle else 0)} | "
            f"{_markdown_cell(str(last_bundle.get('revision_preview_changed_count', 0)) if last_bundle else 0)} |"
        )
        if last_bundle:
            lines.append(
                f"- latest: `{last_bundle['bundle_dir']}` / `{last_bundle['bundle_prefix']}` / "
                f"pending=`{last_bundle['pending_row_count']}` / next=`{last_bundle['next_bundle_exists']}` / "
                f"rerun=`{last_bundle.get('revision_rerun_count', 0)}` / changed=`{last_bundle.get('revision_preview_changed_count', 0)}`"
            )
    return "\n".join(lines) + "\n"


def _structure_inputs(input_set: str) -> tuple[str, ...]:
    if input_set == "basic":
        return DEFAULT_STRUCTURE_INPUTS
    if input_set == "extended":
        return EXTENDED_STRUCTURE_INPUTS
    if input_set == "evaluation":
        return EVALUATION_STRUCTURE_INPUTS
    if input_set == "review":
        return REVIEW_STRUCTURE_INPUTS
    if input_set == "wide":
        return WIDE_STRUCTURE_INPUTS
    raise ValueError(f"unknown input set: {input_set}")


if __name__ == "__main__":
    main()

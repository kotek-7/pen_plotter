from __future__ import annotations

import argparse
import json
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
    build_abx_revision_plan,
    build_abx_responses_from_workbook,
    build_abx_workbook,
    load_abx_responses,
    render_abx_revision_plan_markdown,
    render_abx_revision_run_markdown,
    render_abx_summary_markdown,
    render_abx_workbook_markdown,
    run_abx_revision_loop,
    summarize_abx_responses,
)
from evaluation_harness.human_review_response import (
    load_human_review_responses,
    render_human_review_response_markdown,
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
    human_review.add_argument("--output", default="human_review_packet.md")
    human_review.add_argument("--json-output", default="human_review_packet.json")

    human_feedback = sub.add_parser(
        "human-feedback-loop",
        help="Create a human subjective feedback loop packet and optional response summary",
    )
    human_feedback.add_argument("--root", required=True, help="Run output directory")
    human_feedback.add_argument("--responses-json", help="Human review response JSON")
    human_feedback.add_argument("--reviewer-id", default="")
    human_feedback.add_argument("--output", default="human_feedback_loop.md")
    human_feedback.add_argument("--json-output", default="human_feedback_loop.json")

    human_feedback_ui = sub.add_parser(
        "human-feedback-ui",
        help="Launch a Qt human review UI for the feedback loop",
    )
    target = human_feedback_ui.add_mutually_exclusive_group(required=True)
    target.add_argument("--root", help="Run output directory")
    target.add_argument("--packet-json", help="Existing review packet or loop JSON")
    human_feedback_ui.add_argument("--responses-json", help="Existing human responses JSON")
    human_feedback_ui.add_argument("--summary-json", help="Human review summary output path")
    human_feedback_ui.add_argument("--reviewer-id", default="")

    preview_review = sub.add_parser(
        "preview-review-packet",
        help="Create a preview-centric packet for generated G-code review",
    )
    preview_review.add_argument("--root", required=True, help="Run output directory")
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
        loop = run_preview_revision_loop_fixed_input_set(
            root,
            baseline_generator=args.baseline_generator,
            expected_input_texts=get_evaluation_inputs(args.input_set),
            expected_seeds=tuple(_parse_seeds(args.seeds)),
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
        packet = build_human_review_packet(registry.load_all())
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
        )
        markdown_path = root / args.output
        json_path = root / args.json_output
        markdown_path.write_text(render_human_feedback_loop_markdown(loop), encoding="utf-8")
        json_path.write_text(
            json.dumps(loop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"loop_status: {loop['loop_status']}")
        print(f"representative_count: {loop['packet']['representative_count']}")
        print(f"next_actions: {len(loop['next_actions'])}")
        print(f"report: {markdown_path}")
        print(f"json: {json_path}")
    elif args.command == "human-feedback-ui":
        from evaluation_harness.human_feedback_qt import launch_human_feedback_ui

        root = Path(args.root) if args.root else None
        packet_json = Path(args.packet_json) if args.packet_json else None
        responses_json = Path(args.responses_json) if args.responses_json else None
        summary_json = Path(args.summary_json) if args.summary_json else None
        launch_human_feedback_ui(
            root=root,
            packet_json=packet_json,
            responses_json=responses_json,
            summary_json=summary_json,
            reviewer_id=args.reviewer_id,
        )
    elif args.command == "preview-review-packet":
        root = Path(args.root)
        registry = ExperimentRegistry(root / "registry.jsonl")
        packet = build_human_review_packet(registry.load_all())
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

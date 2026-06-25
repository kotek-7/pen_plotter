from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evaluation_harness.baseline_outline import (
    BaselineOutlineConfig,
    DEFAULT_EVALUATION_INPUTS,
    run_baseline_outline,
)
from evaluation_harness.compare import compare_fixed_input_set, compare_preview_fixed_input_set
from evaluation_harness.human_review import build_human_review_packet
from evaluation_harness.human_review_response import (
    HumanReviewResponse,
    summarize_human_review_responses,
)
from evaluation_harness.models import ExperimentRecord
from evaluation_harness.offline_review import build_offline_review
from evaluation_harness.plot_ready import build_plot_ready_packet
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.reference_basis import build_reference_basis, render_reference_basis_markdown
from evaluation_harness.structure_motion import StructureMotionConfig, run_structure_motion


@dataclass(frozen=True)
class HarnessSelfCheckResult:
    status: str
    run_root: str
    seed: int
    inputs: tuple[str, ...]
    baseline_record_count: int
    candidate_record_count: int
    registry_record_count: int
    baseline_checks: dict[str, Any]
    candidate_checks: dict[str, Any]
    comparison: dict[str, Any]
    preview_comparison: dict[str, Any]
    offline_review: dict[str, Any]
    human_review_packet: dict[str, Any]
    human_review_summary: dict[str, Any]
    plot_ready_packet: dict[str, Any]
    reference_basis: dict[str, Any]
    references: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REFERENCE_SOURCES: tuple[str, ...] = (
    "research/scribing-lab/docs/07_evaluation.md",
    "research/scribing-lab/docs/10_research_flow.md",
)


def run_self_check(root: Path, *, seed: int = 1) -> HarnessSelfCheckResult:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    run_root = _allocate_run_root(root, seed)

    baseline_records = [
        run_baseline_outline(
            root=run_root,
            experiment_id=f"selfcheck-baseline-i{index:02d}-s{seed:03d}",
            input_text=input_text,
            seed=seed,
            config=BaselineOutlineConfig(jitter=0.0, wobble=0.0, optimize=False, vary_speed=False),
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS, start=1)
    ]
    candidate_records = [
        run_structure_motion(
            root=run_root,
            experiment_id=f"selfcheck-candidate-i{index:02d}-s{seed:03d}",
            input_text=input_text,
            seed=seed,
            config=StructureMotionConfig(shape_variation=0.08, layout_variation=0.06),
        )
        for index, input_text in enumerate(DEFAULT_EVALUATION_INPUTS, start=1)
    ]

    registry = ExperimentRegistry(run_root / "registry.jsonl")
    loaded_records = registry.load_all()

    baseline_checks = _build_baseline_checks(baseline_records)
    candidate_checks = _build_candidate_checks(candidate_records)
    comparison = compare_fixed_input_set(
        loaded_records,
        expected_input_texts=DEFAULT_EVALUATION_INPUTS,
        expected_seeds=(seed,),
    )
    preview_comparison = compare_preview_fixed_input_set(
        loaded_records,
        expected_input_texts=DEFAULT_EVALUATION_INPUTS,
        expected_seeds=(seed,),
    )
    offline_review = build_offline_review(candidate_records)
    human_review_packet = build_human_review_packet(candidate_records)
    human_review_summary = summarize_human_review_responses(
        human_review_packet,
        _accept_all_representatives(human_review_packet),
    )
    plot_ready_packet = build_plot_ready_packet(candidate_records, human_review_summary)
    reference_basis = build_reference_basis()

    status = "ok" if _all_checks_pass(baseline_checks, candidate_checks, comparison, preview_comparison, offline_review, human_review_summary, plot_ready_packet, loaded_records, baseline_records, candidate_records) else "needs-review"

    return HarnessSelfCheckResult(
        status=status,
        run_root=str(run_root),
        seed=seed,
        inputs=DEFAULT_EVALUATION_INPUTS,
        baseline_record_count=len(baseline_records),
        candidate_record_count=len(candidate_records),
        registry_record_count=len(loaded_records),
        baseline_checks=baseline_checks,
        candidate_checks=candidate_checks,
        comparison={
            "coverage_ratio": comparison["coverage_ratio"],
            "comparison_count": comparison["comparison_count"],
            "resolved_failure_tags": sorted(
                {
                    tag
                    for item in comparison["comparisons"]
                    for tag in item["resolved_failure_tags"]
                }
            ),
            "baseline_failure_tag_counts": _count_failure_tags(baseline_records),
            "candidate_failure_tag_counts": _count_failure_tags(candidate_records),
        },
        preview_comparison={
            "preview_coverage_ratio": preview_comparison["preview_coverage_ratio"],
            "preview_ready_count": preview_comparison["preview_ready_count"],
            "preview_hash_changed_count": preview_comparison["preview_hash_changed_count"],
        },
        offline_review=offline_review,
        human_review_packet=human_review_packet,
        human_review_summary=human_review_summary,
        plot_ready_packet=plot_ready_packet,
        reference_basis=reference_basis,
        references=REFERENCE_SOURCES,
    )


def render_self_check_markdown(result: HarnessSelfCheckResult) -> str:
    lines = [
        "# Evaluation Harness Self Check",
        "",
        f"- status: `{result.status}`",
        f"- run_root: `{result.run_root}`",
        f"- seed: `{result.seed}`",
        f"- inputs: `{list(result.inputs)}`",
        f"- baseline_record_count: `{result.baseline_record_count}`",
        f"- candidate_record_count: `{result.candidate_record_count}`",
        f"- registry_record_count: `{result.registry_record_count}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in result.baseline_checks.items())
    lines.extend(f"- {name}: `{value}`" for name, value in result.candidate_checks.items())
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- coverage_ratio: `{result.comparison['coverage_ratio']}`",
            f"- comparison_count: `{result.comparison['comparison_count']}`",
            f"- resolved_failure_tags: `{result.comparison['resolved_failure_tags']}`",
            f"- baseline_failure_tag_counts: `{result.comparison['baseline_failure_tag_counts']}`",
            f"- candidate_failure_tag_counts: `{result.comparison['candidate_failure_tag_counts']}`",
            "",
            "## Preview Comparison",
            "",
            f"- preview_coverage_ratio: `{result.preview_comparison['preview_coverage_ratio']}`",
            f"- preview_ready_count: `{result.preview_comparison['preview_ready_count']}`",
            f"- preview_hash_changed_count: `{result.preview_comparison['preview_hash_changed_count']}`",
            "",
            "## Offline Review",
            "",
            f"- robustness: `{result.offline_review['robustness']}`",
            f"- failure_tag_counts: `{result.offline_review['failure_tag_counts']}`",
            "",
            "## Human Review",
            "",
            f"- representative_count: `{result.human_review_packet['representative_count']}`",
            f"- can_proceed_to_plot: `{result.human_review_summary['can_proceed_to_plot']}`",
            "",
            "## Plot Ready",
            "",
            f"- plot_ready_count: `{result.plot_ready_packet['plot_ready_count']}`",
            f"- safety_ok_count: `{result.plot_ready_packet['safety_ok_count']}`",
            "",
            render_reference_basis_markdown(result.reference_basis),
            "",
            "## References",
            "",
        ]
    )
    lines.extend(f"- `{ref}`" for ref in result.references)
    return "\n".join(lines) + "\n"


def _build_baseline_checks(records: list[ExperimentRecord]) -> dict[str, bool]:
    return {
        "baseline_has_expected_record_count": len(records) == len(DEFAULT_EVALUATION_INPUTS),
        "baseline_failure_tags_are_fixed": all(
            set(record.failure_tags) >= {"too-font-like", "terminal-too-uniform"}
            for record in records
        ),
        "baseline_line_mechanical_tags_present": sum(
            "line-too-mechanical" in record.failure_tags for record in records
        )
        == len(DEFAULT_EVALUATION_INPUTS) - 1,
    }


def _build_candidate_checks(records: list[ExperimentRecord]) -> dict[str, bool]:
    return {
        "candidate_has_expected_record_count": len(records) == len(DEFAULT_EVALUATION_INPUTS),
        "candidate_is_plot_safe": all(int(record.metrics.get("gcode_safety_ok", 0)) == 1 for record in records),
        "candidate_has_no_failure_tags": all(not record.failure_tags for record in records),
    }


def _count_failure_tags(records: list[ExperimentRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for tag in record.failure_tags:
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items()))


def _accept_all_representatives(packet: dict[str, Any]) -> list[HumanReviewResponse]:
    return [
        HumanReviewResponse(
            experiment_id=str(item["experiment_id"]),
            decision="accept",
            notes="accepted by self-check",
            reviewer_id="self-check",
        )
        for item in packet["representatives"]
    ]


def _all_checks_pass(
    baseline_checks: dict[str, bool],
    candidate_checks: dict[str, bool],
    comparison: dict[str, Any],
    preview_comparison: dict[str, Any],
    offline_review: dict[str, Any],
    human_review_summary: dict[str, Any],
    plot_ready_packet: dict[str, Any],
    loaded_records: list[ExperimentRecord],
    baseline_records: list[ExperimentRecord],
    candidate_records: list[ExperimentRecord],
) -> bool:
    return (
        all(baseline_checks.values())
        and all(candidate_checks.values())
        and comparison["coverage_ratio"] == 1.0
        and comparison["comparison_count"] == len(DEFAULT_EVALUATION_INPUTS)
        and preview_comparison["preview_coverage_ratio"] == 1.0
        and preview_comparison["preview_ready_count"] == len(DEFAULT_EVALUATION_INPUTS)
        and offline_review["robustness"]["status"] == "ok"
        and human_review_summary["can_proceed_to_plot"] is True
        and plot_ready_packet["plot_ready_count"] == len(plot_ready_packet["items"])
        and plot_ready_packet["plot_ready_count"] == human_review_summary["representative_count"]
        and len(loaded_records) == len(baseline_records) + len(candidate_records)
    )


def _allocate_run_root(root: Path, seed: int) -> Path:
    base = root / f"seed-{seed:03d}"
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return base

    index = 2
    while True:
        candidate = root / f"seed-{seed:03d}-{index:02d}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        index += 1

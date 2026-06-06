from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evaluation_harness.abx import AbxItem, AbxResponse, summarize_abx_responses
from evaluation_harness.baseline_outline import DEFAULT_EVALUATION_INPUTS
from evaluation_harness.compare import compare_preview_fixed_input_set
from evaluation_harness.human_feedback_loop import build_human_feedback_loop
from evaluation_harness.human_review import build_human_review_packet
from evaluation_harness.human_review_response import (
    HumanReviewResponse,
    summarize_human_review_agreement,
    summarize_human_review_calibration,
    summarize_human_review_responses,
)
from evaluation_harness.registry import ExperimentRegistry
from evaluation_harness.self_check import HarnessSelfCheckResult, run_self_check


@dataclass(frozen=True)
class GoalAuditCriterion:
    criterion_id: str
    title: str
    met: bool
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoalAuditResult:
    status: str
    root: str
    seed: int
    criteria: tuple[GoalAuditCriterion, ...]
    self_check: dict[str, Any]
    repeat_self_check: dict[str, Any]
    preview_comparison: dict[str, Any]
    human_feedback_loop: dict[str, Any]
    abx_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["criteria"] = [criterion.to_dict() for criterion in self.criteria]
        return data


def run_goal_audit(root: Path, *, seed: int = 1) -> GoalAuditResult:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    audit_root = root / "goal-audit"
    audit_root.mkdir(parents=True, exist_ok=True)

    first = run_self_check(audit_root, seed=seed)
    second = run_self_check(audit_root, seed=seed)

    preview_comparison = _preview_comparison(first)
    human_feedback_loop = _build_goal_feedback_loop(first)
    abx_summary = _build_goal_abx_summary()
    criteria = _build_goal_criteria(first, second, preview_comparison, human_feedback_loop, abx_summary)
    status = "ready_to_close" if all(criterion.met for criterion in criteria) else "needs_work"

    return GoalAuditResult(
        status=status,
        root=str(root),
        seed=seed,
        criteria=tuple(criteria),
        self_check=_self_check_snapshot(first),
        repeat_self_check=_self_check_snapshot(second),
        preview_comparison=preview_comparison,
        human_feedback_loop=human_feedback_loop,
        abx_summary=abx_summary,
    )


def render_goal_audit_markdown(result: GoalAuditResult) -> str:
    lines = [
        "# Goal Audit",
        "",
        f"- status: `{result.status}`",
        f"- root: `{result.root}`",
        f"- seed: `{result.seed}`",
        "",
        "## Criteria",
        "",
    ]
    for criterion in result.criteria:
        lines.extend(
            [
                f"- {criterion.criterion_id}: `{criterion.title}`",
                f"  - met: `{criterion.met}`",
                f"  - evidence: `{criterion.evidence}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Self Check",
            "",
            f"- first: `{result.self_check}`",
            f"- repeat: `{result.repeat_self_check}`",
            "",
            "## Preview Comparison",
            "",
            f"- preview_similarity: `{result.preview_comparison['preview_similarity']}`",
            f"- preview_ready_count: `{result.preview_comparison['preview_ready_count']}`",
            "",
            "## Human Feedback Loop",
            "",
            f"- loop_status: `{result.human_feedback_loop['loop_status']}`",
            f"- response_summary: `{result.human_feedback_loop['response_summary']}`",
            f"- calibration_summary: `{result.human_feedback_loop['calibration_summary']}`",
            f"- agreement_summary: `{result.human_feedback_loop['agreement_summary']}`",
            f"- next_actions: `{result.human_feedback_loop['next_actions']}`",
            "",
            "## ABX",
            "",
            f"- response_count: `{result.abx_summary['response_count']}`",
            f"- expected_preference_accuracy: `{result.abx_summary['expected_preference_accuracy']}`",
            f"- bradley_terry_ranking: `{result.abx_summary['bradley_terry_ranking']}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _preview_comparison(result: HarnessSelfCheckResult) -> dict[str, Any]:
    registry = ExperimentRegistry(Path(result.run_root) / "registry.jsonl")
    records = registry.load_all()
    comparison = compare_preview_fixed_input_set(
        records,
        expected_input_texts=DEFAULT_EVALUATION_INPUTS,
        expected_seeds=(result.seed,),
    )
    preview_items = comparison["preview_comparisons"]
    return {
        "preview_coverage_ratio": comparison["preview_coverage_ratio"],
        "preview_ready_count": comparison["preview_ready_count"],
        "preview_similarity": preview_items[0]["preview_similarity"] if preview_items else None,
        "preview_similarity_count": sum(
            item["preview_similarity"] is not None for item in preview_items
        ),
        "preview_similarity_keys": sorted(
            {
                key
                for item in preview_items
                if item["preview_similarity"] is not None
                for key in item["preview_similarity"]
            }
        ),
    }


def _build_goal_feedback_loop(result: HarnessSelfCheckResult) -> dict[str, Any]:
    registry = ExperimentRegistry(Path(result.run_root) / "registry.jsonl")
    records = registry.load_all()
    packet = build_human_review_packet(records)
    accept_responses = _accept_all_responses(packet)
    calibration_responses = _calibration_responses(packet)
    agreement_responses = _agreement_responses(packet)
    response_summary = summarize_human_review_responses(packet, accept_responses)
    calibration_summary = summarize_human_review_calibration(packet, calibration_responses)
    agreement_summary = summarize_human_review_agreement(agreement_responses)
    loop = build_human_feedback_loop(
        records,
        responses_data={"responses": [response.to_dict() for response in accept_responses]},
        reviewer_id="goal-audit",
    )
    loop["calibration_summary"] = calibration_summary
    loop["agreement_summary"] = agreement_summary
    return {
        "loop_status": loop["loop_status"],
        "response_summary": response_summary,
        "calibration_summary": calibration_summary,
        "agreement_summary": agreement_summary,
        "next_actions": loop["next_actions"],
        "representative_count": packet["representative_count"],
    }


def _build_goal_abx_summary() -> dict[str, Any]:
    items = [
        AbxItem(
            item_id="item-a",
            prompt="p",
            option_a_artifact="baseline",
            option_b_artifact="candidate",
            question="Which is better?",
            expected_preference="A",
        ),
        AbxItem(
            item_id="item-b",
            prompt="p",
            option_a_artifact="baseline",
            option_b_artifact="candidate",
            question="Which is better?",
            expected_preference="A",
        ),
    ]
    responses = [
        AbxResponse(item_id="item-a", evaluator_id="eval-1", choice="A", confidence=4),
        AbxResponse(item_id="item-a", evaluator_id="eval-2", choice="A", confidence=3),
        AbxResponse(item_id="item-b", evaluator_id="eval-1", choice="A", confidence=5),
        AbxResponse(item_id="item-b", evaluator_id="eval-2", choice="tie", confidence=2),
    ]
    return summarize_abx_responses(responses, items=items)


def _build_goal_criteria(
    first: HarnessSelfCheckResult,
    second: HarnessSelfCheckResult,
    preview_comparison: dict[str, Any],
    human_feedback_loop: dict[str, Any],
    abx_summary: dict[str, Any],
) -> list[GoalAuditCriterion]:
    criteria: list[GoalAuditCriterion] = []

    criteria.append(
        GoalAuditCriterion(
            criterion_id="self-check-repeatable",
            title="固定入力セットの self-check が再実行可能で、主要サマリが一致する",
            met=_self_check_snapshot(first) == _self_check_snapshot(second),
            evidence={
                "first": _self_check_snapshot(first),
                "repeat": _self_check_snapshot(second),
            },
        )
    )
    criteria.append(
        GoalAuditCriterion(
            criterion_id="external-methods-wired",
            title="SSIM / kappa / Bradley-Terry / uncertainty sampling の接続点がある",
            met=(
                "ssim_proxy" in preview_comparison["preview_similarity_keys"]
                and human_feedback_loop["calibration_summary"]["recommended_adjustments"]
                and human_feedback_loop["agreement_summary"]["mean_cohen_kappa"] is not None
                and abx_summary["bradley_terry_ranking"]
            ),
            evidence={
                "preview_similarity_keys": preview_comparison["preview_similarity_keys"],
                "calibration_recommendations": human_feedback_loop["calibration_summary"][
                    "recommended_adjustments"
                ],
                "mean_cohen_kappa": human_feedback_loop["agreement_summary"]["mean_cohen_kappa"],
                "bradley_terry_ranking": abx_summary["bradley_terry_ranking"],
            },
        )
    )
    criteria.append(
        GoalAuditCriterion(
            criterion_id="human-feedback-loop-wired",
            title="human feedback loop が response / calibration / agreement を返す",
            met=(
                human_feedback_loop["response_summary"]["can_proceed_to_plot"] is True
                and human_feedback_loop["calibration_summary"]["reviewed_response_count"] > 0
                and human_feedback_loop["agreement_summary"]["reviewer_count"] >= 2
                and bool(human_feedback_loop["next_actions"])
            ),
            evidence={
                "loop_status": human_feedback_loop["loop_status"],
                "response_summary": human_feedback_loop["response_summary"],
                "calibration_summary": human_feedback_loop["calibration_summary"],
                "agreement_summary": human_feedback_loop["agreement_summary"],
                "next_actions": human_feedback_loop["next_actions"],
            },
        )
    )
    criteria.append(
        GoalAuditCriterion(
            criterion_id="uncertainty-prioritized",
            title="不確実な候補が human review の代表選定に入る",
            met=(
                bool(first.human_review_packet["robustness"]["uncertain_record_ids"])
                and first.human_review_packet["representatives"][0]["experiment_id"]
                in first.human_review_packet["robustness"]["uncertain_record_ids"]
            ),
            evidence={
                "uncertain_record_ids": first.human_review_packet["robustness"][
                    "uncertain_record_ids"
                ],
                "first_representative": first.human_review_packet["representatives"][0][
                    "experiment_id"
                ]
                if first.human_review_packet["representatives"]
                else None,
            },
        )
    )
    criteria.append(
        GoalAuditCriterion(
            criterion_id="regression-gate",
            title="preview / offline review / plot-ready の回帰ゲートが閉じる",
            met=(
                first.status == "ok"
                and first.comparison["coverage_ratio"] == 1.0
                and first.preview_comparison["preview_coverage_ratio"] == 1.0
                and first.offline_review["robustness"]["status"] == "ok"
                and first.human_review_summary["can_proceed_to_plot"] is True
                and first.plot_ready_packet["plot_ready_count"] == len(first.plot_ready_packet["items"])
            ),
            evidence={
                "self_check_status": first.status,
                "comparison_coverage_ratio": first.comparison["coverage_ratio"],
                "preview_coverage_ratio": first.preview_comparison["preview_coverage_ratio"],
                "offline_review_status": first.offline_review["robustness"]["status"],
                "human_review_can_proceed_to_plot": first.human_review_summary["can_proceed_to_plot"],
                "plot_ready_count": first.plot_ready_packet["plot_ready_count"],
            },
        )
    )

    return criteria


def _self_check_snapshot(result: HarnessSelfCheckResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "baseline_record_count": result.baseline_record_count,
        "candidate_record_count": result.candidate_record_count,
        "registry_record_count": result.registry_record_count,
        "comparison": {
            "coverage_ratio": result.comparison["coverage_ratio"],
            "comparison_count": result.comparison["comparison_count"],
            "resolved_failure_tags": tuple(result.comparison["resolved_failure_tags"]),
        },
        "preview_comparison": {
            "preview_coverage_ratio": result.preview_comparison["preview_coverage_ratio"],
            "preview_ready_count": result.preview_comparison["preview_ready_count"],
            "preview_hash_changed_count": result.preview_comparison["preview_hash_changed_count"],
        },
        "offline_review": {
            "status": result.offline_review["robustness"]["status"],
            "failure_tag_counts": tuple(sorted(result.offline_review["failure_tag_counts"].items())),
        },
        "human_review_packet": {
            "representative_count": result.human_review_packet["representative_count"],
            "uncertain_record_ids": tuple(
                result.human_review_packet["robustness"].get("uncertain_record_ids", [])
            ),
        },
        "human_review_summary": {
            "can_proceed_to_plot": result.human_review_summary["can_proceed_to_plot"],
            "decision_counts": tuple(sorted(result.human_review_summary["decision_counts"].items())),
        },
        "plot_ready_packet": {
            "plot_ready_count": result.plot_ready_packet["plot_ready_count"],
            "safety_ok_count": result.plot_ready_packet["safety_ok_count"],
        },
        "reference_basis": {
            "source_count": result.reference_basis["source_count"],
            "axis_count": result.reference_basis["axis_count"],
        },
    }


def _accept_all_responses(packet: dict[str, Any]) -> list[HumanReviewResponse]:
    responses: list[HumanReviewResponse] = []
    for item in packet.get("representatives", []):
        responses.append(
            HumanReviewResponse(
                experiment_id=str(item["experiment_id"]),
                decision="accept",
                notes="goal-audit fixture",
                reviewer_id="goal-audit-reviewer",
            )
        )
    return responses


def _calibration_responses(packet: dict[str, Any]) -> list[HumanReviewResponse]:
    responses: list[HumanReviewResponse] = []
    for index, item in enumerate(packet.get("representatives", [])):
        tags = [str(tag) for tag in item.get("failure_tags", [])]
        if tags and index % 2 == 0:
            responses.append(
                HumanReviewResponse(
                    experiment_id=str(item["experiment_id"]),
                    decision="needs-tuning",
                    reason_tags=[tags[0]],
                    notes="goal-audit calibration fixture",
                    reviewer_id="goal-audit-reviewer",
                )
            )
        elif tags:
            responses.append(
                HumanReviewResponse(
                    experiment_id=str(item["experiment_id"]),
                    decision="reject",
                    reason_tags=[tags[0]],
                    notes="goal-audit calibration fixture",
                    reviewer_id="goal-audit-reviewer",
                )
            )
        else:
            responses.append(
                HumanReviewResponse(
                    experiment_id=str(item["experiment_id"]),
                    decision="accept",
                    notes="goal-audit calibration fixture",
                    reviewer_id="goal-audit-reviewer",
                )
            )
    return responses


def _agreement_responses(packet: dict[str, Any]) -> list[HumanReviewResponse]:
    responses: list[HumanReviewResponse] = []
    representative_ids = [str(item["experiment_id"]) for item in packet.get("representatives", [])]
    for index, experiment_id in enumerate(representative_ids):
        decision = "accept" if index % 2 == 0 else "needs-tuning"
        reason_tags = ["spacing-too-wide"] if decision != "accept" else []
        responses.append(
            HumanReviewResponse(
                experiment_id=experiment_id,
                decision=decision,
                reason_tags=reason_tags,
                notes="goal-audit agreement fixture",
                reviewer_id="reviewer-a",
            )
        )
        responses.append(
            HumanReviewResponse(
                experiment_id=experiment_id,
                decision=decision if index % 3 else "accept",
                reason_tags=reason_tags if decision != "accept" else [],
                notes="goal-audit agreement fixture",
                reviewer_id="reviewer-b",
            )
        )
    return responses

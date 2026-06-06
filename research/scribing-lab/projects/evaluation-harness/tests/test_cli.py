from pathlib import Path

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
    assert args.output == "fixed.md"
    assert args.json_output == "fixed.json"


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


def _record(
    *,
    experiment_id: str,
    input_text: str,
    seed: int,
    generator: str,
    metrics: dict[str, float | int | str] | None = None,
    failure_tags: list[str] | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        hypothesis="test",
        input_text=input_text,
        profile_id="baseline-neat",
        seed=seed,
        generator=generator,
        exporter="xdraw-gcode",
        artifacts={"report": f"artifacts/{experiment_id}/report.md"},
        metrics=metrics or {"duration_ms": 1000, "stroke_count": 1},
        failure_tags=failure_tags or [],
        next_action="validate fixed input comparison",
    )

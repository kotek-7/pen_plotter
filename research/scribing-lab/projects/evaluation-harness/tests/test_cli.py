from pathlib import Path

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

from evaluation_harness.cli import build_parser


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

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

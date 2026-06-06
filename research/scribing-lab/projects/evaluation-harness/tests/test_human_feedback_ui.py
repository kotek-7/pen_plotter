from evaluation_harness.human_feedback_ui import (
    _choose_font_family,
    build_common_failure_examples,
    build_decision_help,
    build_review_instructions,
)


def test_choose_font_family_prefers_first_available_candidate() -> None:
    family = _choose_font_family(
        {"Meiryo", "DejaVu Sans"},
        ("Yu Gothic", "Meiryo", "DejaVu Sans"),
    )

    assert family == "Meiryo"


def test_choose_font_family_is_case_insensitive() -> None:
    family = _choose_font_family(
        {"nimbus sans l", "nimbus mono l"},
        ("Nimbus Sans L", "Nimbus Mono L"),
    )

    assert family == "nimbus sans l"


def test_choose_font_family_falls_back_to_tk_default_font() -> None:
    family = _choose_font_family({"Unrelated Font"}, ("Yu Gothic", "Meiryo"))

    assert family == "TkDefaultFont"


def test_build_review_instructions_are_stepwise() -> None:
    instructions = build_review_instructions()

    assert instructions[0].startswith("1.")
    assert len(instructions) == 4
    assert "Export Responses" in instructions[-1]


def test_build_decision_help_mentions_all_decisions() -> None:
    help_lines = build_decision_help()

    assert any(line.startswith("accept:") for line in help_lines)
    assert any(line.startswith("needs-tuning:") for line in help_lines)
    assert any(line.startswith("reject:") for line in help_lines)


def test_build_common_failure_examples_cover_known_problems() -> None:
    examples = build_common_failure_examples()

    assert any("文字が小さすぎる" in line for line in examples)
    assert any("字間" in line for line in examples)
    assert any("ひっくり返る" in line for line in examples)

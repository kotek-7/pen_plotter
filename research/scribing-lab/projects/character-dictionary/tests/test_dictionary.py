import pytest

from character_dictionary import (
    BUILTIN_CHARACTERS,
    BUILTIN_CHARACTER_ORDER,
    LayoutConfig,
    DICTIONARY_ID,
    SCHEMA_VERSION,
    export_dictionary,
    export_dictionary_json,
    get_template,
    iter_builtin_templates,
    layout_text,
    map_stroke_type_to_terminal,
)


def test_get_template_returns_ordered_strokes_for_ei() -> None:
    template = get_template("永")

    assert template.char_id == "U+6C38"
    assert len(template.strokes) == 5
    assert [stroke.order for stroke in template.strokes] == [1, 2, 3, 4, 5]
    assert {stroke.terminal for stroke in template.strokes} >= {"tome", "harai"}


def test_layout_text_places_points_in_a4_coordinates() -> None:
    strokes = layout_text("あい", LayoutConfig(char_size=10.0, margin_left=12.0, margin_top=16.0))

    assert strokes
    xs = [x for stroke in strokes for x, _ in stroke.points]
    ys = [y for stroke in strokes for _, y in stroke.points]
    assert min(xs) >= 0.0
    assert max(xs) <= 210.0
    assert min(ys) >= 0.0
    assert max(ys) <= 297.0
    assert strokes[0].literal == "あ"
    assert any(stroke.literal == "い" for stroke in strokes)


def test_layout_text_shape_variation_is_disabled_by_default() -> None:
    default_strokes = layout_text("永", LayoutConfig())
    explicit_strokes = layout_text("永", LayoutConfig(shape_variation=0.0, variation_seed=42))

    assert [stroke.points for stroke in default_strokes] == [
        stroke.points for stroke in explicit_strokes
    ]


def test_layout_text_shape_variation_is_seeded() -> None:
    config = LayoutConfig(shape_variation=0.08, variation_seed=7)

    first = layout_text("永", config)
    second = layout_text("永", config)

    assert [stroke.points for stroke in first] == [stroke.points for stroke in second]


def test_layout_text_shape_variation_changes_points() -> None:
    default_strokes = layout_text("永", LayoutConfig())
    varied_strokes = layout_text("永", LayoutConfig(shape_variation=0.08, variation_seed=7))

    assert [stroke.points for stroke in default_strokes] != [
        stroke.points for stroke in varied_strokes
    ]


def test_layout_text_layout_variation_is_seeded() -> None:
    config = LayoutConfig(layout_variation=0.12, variation_seed=7)

    first = layout_text("あいうえお", config)
    second = layout_text("あいうえお", config)

    assert [stroke.points for stroke in first] == [stroke.points for stroke in second]


def test_layout_text_layout_variation_changes_character_positions() -> None:
    default_strokes = layout_text("あいうえお", LayoutConfig())
    varied_strokes = layout_text("あいうえお", LayoutConfig(layout_variation=0.12, variation_seed=7))

    assert [stroke.points for stroke in default_strokes] != [
        stroke.points for stroke in varied_strokes
    ]


def test_layout_text_line_variation_changes_second_line() -> None:
    default_strokes = layout_text("あ\nあ", LayoutConfig())
    varied_strokes = layout_text("あ\nあ", LayoutConfig(layout_variation=0.12, variation_seed=7))

    assert default_strokes[3].points != varied_strokes[3].points


def test_layout_text_slant_changes_x_offsets() -> None:
    default_strokes = layout_text("永", LayoutConfig())
    slanted_strokes = layout_text("永", LayoutConfig(slant_deg=10.0))

    default_points = default_strokes[2].points
    slanted_points = slanted_strokes[2].points

    assert slanted_points[0][0] != default_points[0][0]
    assert slanted_points[-1][0] != default_points[-1][0]
    assert slanted_points[-1][0] - default_points[-1][0] > slanted_points[0][0] - default_points[0][0]


def test_layout_text_baseline_drift_moves_lower_lines() -> None:
    default_strokes = layout_text("永\n永", LayoutConfig())
    drifted_strokes = layout_text("永\n永", LayoutConfig(baseline_drift_mm=1.0))

    default_second_line_y = min(y for _, y in default_strokes[5].points)
    drifted_second_line_y = min(y for _, y in drifted_strokes[5].points)

    assert drifted_second_line_y < default_second_line_y


def test_layout_text_falls_back_for_unknown_character() -> None:
    strokes = layout_text("今", LayoutConfig())

    assert strokes
    assert all(stroke.literal == "今" for stroke in strokes)
    assert all(stroke.terminal == "none" for stroke in strokes)


def test_builtin_dictionary_covers_minimum_evaluation_subset() -> None:
    assert {"永", "あ", "い", "う", "え", "お"} <= BUILTIN_CHARACTERS


def test_builtin_character_order_is_stable() -> None:
    assert BUILTIN_CHARACTER_ORDER == ("永", "あ", "い", "う", "え", "お")
    assert [template.literal for template in iter_builtin_templates()] == list(
        BUILTIN_CHARACTER_ORDER
    )


def test_export_dictionary_is_normalized_and_deterministic() -> None:
    first = export_dictionary()
    second = export_dictionary()

    assert first == second
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["dictionary_id"] == DICTIONARY_ID
    assert first["character_count"] == len(BUILTIN_CHARACTER_ORDER)
    assert [item["literal"] for item in first["characters"]] == list(BUILTIN_CHARACTER_ORDER)
    assert [item["strokes"][0]["stroke_id"] for item in first["characters"] if item["strokes"]] == [
        1,
        1,
        1,
        1,
        1,
        1,
    ]


def test_export_dictionary_json_is_stable() -> None:
    json_text = export_dictionary_json()

    assert '"schema_version": 1' in json_text
    assert '"dictionary_id": "manual-kanjivg-mvp"' in json_text
    assert json_text.endswith("\n")


@pytest.mark.parametrize(
    ("stroke_type", "terminal"),
    [
        ("ten", "tome"),
        ("yoko", "tome"),
        ("hidari", "harai"),
        ("migi", "harai"),
        ("hane", "hane"),
        ("unknown", "none"),
    ],
)
def test_map_stroke_type_to_terminal(stroke_type: str, terminal: str) -> None:
    assert map_stroke_type_to_terminal(stroke_type) == terminal

import pytest

from character_dictionary import (
    BUILTIN_CHARACTERS,
    DictionaryLookupError,
    LayoutConfig,
    get_template,
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


def test_layout_text_rejects_unknown_character() -> None:
    with pytest.raises(DictionaryLookupError):
        layout_text("未")


def test_builtin_dictionary_covers_minimum_evaluation_subset() -> None:
    assert {"永", "あ", "い", "う", "え", "お"} <= BUILTIN_CHARACTERS


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

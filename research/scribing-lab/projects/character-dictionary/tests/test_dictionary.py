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


@pytest.mark.parametrize("literal", ["あ", "い", "う", "え", "お"])
def test_kana_templates_are_font_outlines(literal: str) -> None:
    template = get_template(literal)

    assert template.source == "font-outline"
    assert template.strokes
    assert all(stroke.stroke_type == "outline" for stroke in template.strokes)
    assert all(stroke.terminal == "none" for stroke in template.strokes)

    xs = [x for stroke in template.strokes for x, _ in stroke.skeleton_points]
    ys = [y for stroke in template.strokes for _, y in stroke.skeleton_points]
    assert min(xs) >= 0.0
    assert max(xs) <= 1.0
    assert min(ys) >= 0.0
    assert max(ys) <= 1.0


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


def test_layout_text_fit_to_page_scales_long_lines_into_paper_width() -> None:
    text = "この文章は、手書きらしさ、速度変動、終筆の違いをまとめて観察するためのものです。"
    default_strokes = layout_text(
        text,
        LayoutConfig(char_size=9.2, char_spacing=1.6, margin_left=12.0, margin_top=16.0),
    )
    fitted_strokes = layout_text(
        text,
        LayoutConfig(
            char_size=9.2,
            char_spacing=1.6,
            margin_left=12.0,
            margin_top=16.0,
            fit_to_page=True,
        ),
    )

    default_xs = [x for stroke in default_strokes for x, _ in stroke.points]
    fitted_xs = [x for stroke in fitted_strokes for x, _ in stroke.points]

    assert max(default_xs) > 210.0
    assert max(fitted_xs) <= 210.0
    assert max(fitted_xs) < max(default_xs)


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
    assert min(x for stroke in strokes for x, _ in stroke.points) >= 0.0
    assert max(x for stroke in strokes for x, _ in stroke.points) <= 210.0
    assert min(y for stroke in strokes for _, y in stroke.points) >= 0.0
    assert max(y for stroke in strokes for _, y in stroke.points) <= 297.0


def test_builtin_dictionary_covers_minimum_evaluation_subset() -> None:
    assert {"永", "あ", "い", "う", "え", "お"} <= BUILTIN_CHARACTERS
    assert {"今", "日", "本", "天", "気", "春", "川", "歩", "、", "。"} <= BUILTIN_CHARACTERS
    assert {"が", "っ", "ア", "レ", "ビ", "ュ"} <= BUILTIN_CHARACTERS


def test_builtin_dictionary_covers_fixed_evaluation_inputs() -> None:
    texts = [
        "永",
        "あいうえお",
        "今日はよい天気です。",
        "春の川をゆっくり歩く。",
        "本日はありがとうございました。",
        "文字列の品質を評価するために、少し長めの文章を用意します。",
        "同じ文字が続くときのばらつきと、字間の自然さを確認する。",
        "評価器の人間レビューでは、候補ごとの差が読み取れることが重要です。",
        "一行だけでなく、複数の文や改行を含むケースも確認する。\nここでは行間と整列も見る。",
        "この文章は、手書きらしさ、速度変動、終筆の違いをまとめて観察するためのものです。",
        "ああああいいううええおおお",
        "長文の比較に十分な余白と字数を持たせるため、ここでは少しだけ冗長に書いています。",
    ]
    missing = sorted(
        {
            char
            for text in texts
            for char in text
            if not char.isspace() and char not in BUILTIN_CHARACTERS
        }
    )

    assert missing == []


def test_builtin_character_order_is_stable() -> None:
    assert BUILTIN_CHARACTER_ORDER[:6] == ("永", "あ", "い", "う", "え", "お")
    assert len(BUILTIN_CHARACTER_ORDER) > 6
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
    assert all(item["strokes"] for item in first["characters"])
    assert [item["strokes"][0]["stroke_id"] for item in first["characters"] if item["strokes"]][
        :6
    ] == [1, 1, 1, 1, 1, 1]


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

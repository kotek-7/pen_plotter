from __future__ import annotations

from typing import Final


SCRIPT_GROUP_KANA: Final = "kana"
SCRIPT_GROUP_KANJI: Final = "kanji"
SCRIPT_GROUP_LATIN: Final = "latin"
SCRIPT_GROUP_DIGIT: Final = "digit"
SCRIPT_GROUP_PUNCTUATION: Final = "punctuation"
SCRIPT_GROUP_SYMBOL: Final = "symbol"
SCRIPT_GROUP_OTHER: Final = "other"

SCRIPT_GROUP_PRIORITY: tuple[str, ...] = (
    SCRIPT_GROUP_KANA,
    SCRIPT_GROUP_KANJI,
    SCRIPT_GROUP_LATIN,
    SCRIPT_GROUP_DIGIT,
    SCRIPT_GROUP_PUNCTUATION,
    SCRIPT_GROUP_SYMBOL,
    SCRIPT_GROUP_OTHER,
)

JAPANESE_FONT_CANDIDATES: tuple[str, ...] = (
    "Noto Sans CJK JP",
    "Noto Serif CJK JP",
    "IPAexGothic",
    "IPAGothic",
    "Yu Gothic",
    "Meiryo",
    "TakaoGothic",
    "DejaVu Sans",
)

LATIN_FONT_CANDIDATES: tuple[str, ...] = (
    "Comic Neue",
    "Ubuntu Sans",
    "FreeSans",
    "Open Sans",
    "Liberation Sans",
    "Noto Sans",
    "Noto Sans Mono",
    "DejaVu Sans",
    "DejaVu Sans Mono",
    "Nimbus Sans",
    "Nimbus Mono PS",
    "Helvetica",
    "Arial",
)

SMALL_KANA_LITERALS = frozenset("ぁぃぅぇぉゃゅょっゎゕゖァィゥェォャュョッヮヵヶ")
SMALL_PUNCTUATION_LITERALS = frozenset("、。，．・")
FULL_WIDTH_PUNCTUATION_LITERALS = frozenset("！？!?")


def classify_character(literal: str) -> str:
    if not literal:
        return SCRIPT_GROUP_OTHER
    char = literal[0]
    if char.isspace():
        return SCRIPT_GROUP_OTHER
    if "0" <= char <= "9":
        return SCRIPT_GROUP_DIGIT
    if "A" <= char <= "Z" or "a" <= char <= "z":
        return SCRIPT_GROUP_LATIN
    if "ぁ" <= char <= "ゟ":
        return SCRIPT_GROUP_KANA
    if "ァ" <= char <= "ヿ":
        return SCRIPT_GROUP_KANA
    if "一" <= char <= "龯":
        return SCRIPT_GROUP_KANJI
    if char in "。、，．！？「」『』・ー,.;:!?-()[]{}<>/\\":
        return SCRIPT_GROUP_PUNCTUATION
    if char in "@#$%&*+=~^_|`'\"":
        return SCRIPT_GROUP_SYMBOL
    return SCRIPT_GROUP_OTHER


def character_display_scale(
    literal: str,
    *,
    script_group: str | None = None,
    source: str = "",
) -> float:
    group = script_group or classify_character(literal)
    if literal in SMALL_KANA_LITERALS:
        return 0.48
    if literal in SMALL_PUNCTUATION_LITERALS:
        return 0.40
    if literal == "ー":
        return 0.74
    if literal in FULL_WIDTH_PUNCTUATION_LITERALS:
        return 0.60
    if group in {SCRIPT_GROUP_KANA, SCRIPT_GROUP_KANJI}:
        return 1.0
    if group == SCRIPT_GROUP_LATIN:
        return 0.94 if source == "font-outline" else 0.92
    if group == SCRIPT_GROUP_DIGIT:
        return 0.88
    if group == SCRIPT_GROUP_PUNCTUATION:
        return 0.52 if source == "font-outline" else 0.48
    if group == SCRIPT_GROUP_SYMBOL:
        return 0.72
    return 1.0


def character_advance_ratio(
    literal: str,
    *,
    script_group: str | None = None,
    source: str = "",
) -> float:
    group = script_group or classify_character(literal)
    if literal in SMALL_KANA_LITERALS:
        return 0.42
    if literal in SMALL_PUNCTUATION_LITERALS:
        return 0.28
    if literal == "ー":
        return 0.72
    if literal in FULL_WIDTH_PUNCTUATION_LITERALS:
        return 0.44
    if group == SCRIPT_GROUP_KANA:
        return 0.9
    if group == SCRIPT_GROUP_KANJI:
        return 0.92 if source == "font-outline" else 0.9
    if group == SCRIPT_GROUP_LATIN:
        return 0.70
    if group == SCRIPT_GROUP_DIGIT:
        return 0.74
    if group == SCRIPT_GROUP_PUNCTUATION:
        return 0.36
    if group == SCRIPT_GROUP_SYMBOL:
        return 0.50
    return 0.9


def character_shape_variation_scale(literal: str, *, script_group: str | None = None) -> float:
    group = script_group or classify_character(literal)
    if literal in SMALL_KANA_LITERALS:
        return 0.03
    if literal in SMALL_PUNCTUATION_LITERALS:
        return 0.0
    if literal == "ー":
        return 0.03
    if group == SCRIPT_GROUP_LATIN:
        return 0.0
    if group == SCRIPT_GROUP_DIGIT:
        return 0.0
    if group == SCRIPT_GROUP_PUNCTUATION:
        return 0.0
    if group == SCRIPT_GROUP_SYMBOL:
        return 0.0
    return 1.0


def character_layout_offset(
    literal: str,
    *,
    script_group: str | None = None,
) -> tuple[float, float]:
    group = script_group or classify_character(literal)
    if literal in SMALL_KANA_LITERALS:
        return (0.01, -0.16)
    if literal in SMALL_PUNCTUATION_LITERALS:
        return (0.10, -0.22)
    if literal == "ー":
        return (0.02, -0.06)
    if literal in FULL_WIDTH_PUNCTUATION_LITERALS:
        return (0.04, -0.12)
    if group in {SCRIPT_GROUP_LATIN, SCRIPT_GROUP_DIGIT, SCRIPT_GROUP_PUNCTUATION, SCRIPT_GROUP_SYMBOL}:
        return (0.0, 0.0)
    return (0.0, 0.0)


def font_candidates_for_character(literal: str) -> tuple[str, ...]:
    group = classify_character(literal)
    if group in {SCRIPT_GROUP_KANA, SCRIPT_GROUP_KANJI, SCRIPT_GROUP_OTHER}:
        return JAPANESE_FONT_CANDIDATES
    if group in {SCRIPT_GROUP_LATIN, SCRIPT_GROUP_DIGIT, SCRIPT_GROUP_PUNCTUATION, SCRIPT_GROUP_SYMBOL}:
        return LATIN_FONT_CANDIDATES
    return JAPANESE_FONT_CANDIDATES

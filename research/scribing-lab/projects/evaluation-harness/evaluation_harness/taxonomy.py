FAILURE_TAGS: frozenset[str] = frozenset(
    {
        "unreadable",
        "wrong-stroke-order",
        "too-uniform",
        "over-jittered",
        "spacing-unnatural",
        "terminal-too-uniform",
        "penup-artifact",
        "plotter-unsafe",
        "profile-inconsistent",
        "too-font-like",
        "too-small",
        "skeleton-too-rigid",
        "line-too-mechanical",
        "paragraph-spacing-unnatural",
        "spacing-too-wide",
        "repeated-char-too-identical",
        "glyph-orientation-odd",
        "scan-mismatch",
        "plotter-line-quality-bad",
    }
)


def validate_failure_tags(tags: list[str]) -> None:
    unknown = sorted(set(tags) - FAILURE_TAGS)
    if unknown:
        raise ValueError(f"Unknown failure tags: {', '.join(unknown)}")

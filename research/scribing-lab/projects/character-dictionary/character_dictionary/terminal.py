HARAI_TYPES = {"hidari", "migi"}
HANE_TYPES = {"hane"}
TOME_TYPES = {"ten", "yoko", "tate", "ori"}


def map_stroke_type_to_terminal(stroke_type: str) -> str:
    if stroke_type in HARAI_TYPES:
        return "harai"
    if stroke_type in HANE_TYPES:
        return "hane"
    if stroke_type in TOME_TYPES:
        return "tome"
    return "none"

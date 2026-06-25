HARAI_TYPES = {
    "hidari",
    "migi",
    "㇀",
    "㇁",
    "㇂",
    "㇒",
    "㇓",
    "㇏",
    "㇇",
}
HANE_TYPES = {"hane", "㇆", "㇈", "㇉", "㇙", "㇛", "㇜", "㇟"}
TOME_TYPES = {
    "ten",
    "yoko",
    "tate",
    "ori",
    "㇔",
    "㇐",
    "㇑",
    "㇕",
    "㇖",
    "㇗",
}


def _split_stroke_types(stroke_type: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in stroke_type.split("/") if part.strip())


def map_stroke_type_to_terminal(stroke_type: str) -> str:
    parts = _split_stroke_types(stroke_type) or (stroke_type,)
    if any(part in HARAI_TYPES for part in parts):
        return "harai"
    if any(part in HANE_TYPES for part in parts):
        return "hane"
    if any(part in TOME_TYPES for part in parts):
        return "tome"
    return "none"

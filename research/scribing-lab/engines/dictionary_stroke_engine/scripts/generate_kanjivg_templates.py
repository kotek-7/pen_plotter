from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


KANJIVG_RELEASE = "20250816"
KANJIVG_TAG = f"r{KANJIVG_RELEASE}"
KANJIVG_URL = (
    f"https://github.com/KanjiVG/kanjivg/releases/download/{KANJIVG_TAG}/"
    f"kanjivg-{KANJIVG_RELEASE}-main.zip"
)
KANJIVG_LICENSE = "CC BY-SA 3.0"
KANJIVG_SOURCE = "kanjivg"
SAMPLES_PER_SEGMENT = 10

TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtZz]|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the full KanjiVG template asset for dictionary_stroke_engine.")
    parser.add_argument("--zip", type=Path, help="KanjiVG main release zip. Defaults to downloading the pinned release.")
    parser.add_argument("--url", default=KANJIVG_URL, help="KanjiVG zip URL used when --zip is omitted.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "kanjivg_templates.json",
        help="Output JSON asset path.",
    )
    args = parser.parse_args()

    if args.zip is None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "kanjivg-main.zip"
            _download(args.url, zip_path)
            asset = build_asset(zip_path, source_url=args.url)
    else:
        asset = build_asset(args.zip, source_url=args.url)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asset, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} ({asset['character_count']} characters)")


def _download(url: str, path: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
        path.write_bytes(response.read())


def build_asset(zip_path: Path, *, source_url: str) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    with ZipFile(zip_path) as archive:
        svg_names = sorted(name for name in archive.namelist() if name.startswith("kanji/") and name.endswith(".svg"))
        for name in svg_names:
            literal = _literal_from_svg_name(name)
            try:
                svg_text = archive.read(name).decode("utf-8")
                entries.append(_template_entry(literal, svg_text))
            except Exception as exc:  # noqa: BLE001
                errors.append({"file": name, "literal": literal, "error": str(exc)})

    return {
        "schema_version": 1,
        "source": KANJIVG_SOURCE,
        "source_url": source_url,
        "release": KANJIVG_TAG,
        "license": KANJIVG_LICENSE,
        "character_count": len(entries),
        "error_count": len(errors),
        "errors": errors,
        "characters": entries,
    }


def _literal_from_svg_name(name: str) -> str:
    codepoint = Path(name).stem
    return chr(int(codepoint, 16))


def _template_entry(literal: str, svg_text: str) -> dict[str, object]:
    strokes, bbox = _parse_svg_template(svg_text)
    if not strokes:
        raise ValueError("no stroke paths found")
    script_group = _classify_script(literal)
    return {
        "advance_ratio": _advance_ratio(literal, script_group=script_group),
        "bbox": list(bbox),
        "char_id": f"U+{ord(literal):04X}",
        "display_scale": _display_scale(literal, script_group=script_group),
        "license": KANJIVG_LICENSE,
        "literal": literal,
        "script_group": script_group,
        "source": KANJIVG_SOURCE,
        "strokes": strokes,
    }


def _parse_svg_template(svg_text: str) -> tuple[list[dict[str, object]], tuple[float, float, float, float]]:
    root = ET.fromstring(svg_text)
    view_box = _view_box(root)
    stroke_paths_group = _find_stroke_paths_group(root)
    path_elements = [element for element in stroke_paths_group.iter() if _local_name(element.tag) == "path"]

    sampled_strokes: list[list[tuple[float, float]]] = []
    raw_strokes: list[dict[str, object]] = []
    for index, path_element in enumerate(path_elements, start=1):
        d = path_element.get("d", "").strip()
        if not d:
            continue
        sampled_points = _sample_path(d)
        if len(sampled_points) < 2:
            continue
        raw_type = _attribute(path_element, "type", default="")
        sampled_strokes.append(sampled_points)
        raw_strokes.append(
            {
                "confidence": 1.0,
                "order": index,
                "path": d,
                "stroke_id": index,
                "stroke_type": raw_type or "none",
                "terminal": _terminal_for(raw_type),
            }
        )

    normalized_strokes = _normalize_strokes_to_view_box(sampled_strokes, view_box)
    if len(normalized_strokes) != len(raw_strokes):
        raise ValueError("stroke count mismatch")

    strokes: list[dict[str, object]] = []
    for raw, points in zip(raw_strokes, normalized_strokes, strict=True):
        strokes.append({**raw, "skeleton_points": [[_round_unit(x), _round_unit(y)] for x, y in points]})
    return strokes, tuple(_round_unit(value) for value in _bbox_from_strokes(normalized_strokes))


def _sample_path(d: str) -> list[tuple[float, float]]:
    tokens = TOKEN_RE.findall(d)
    if not tokens:
        return []

    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_cubic_control: tuple[float, float] | None = None
    prev_quadratic_control: tuple[float, float] | None = None
    command: str | None = None
    index = 0

    def read_number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    def read_pair() -> tuple[float, float]:
        return (read_number(), read_number())

    while index < len(tokens):
        token = tokens[index]
        if token in "MmLlHhVvCcSsQqTtZz":
            command = token
            index += 1
            if token in "Zz":
                current = start
                prev_cubic_control = None
                prev_quadratic_control = None
                continue
        if command is None:
            raise ValueError(f"path data missing command in {d!r}")

        if command in "Mm":
            point = read_pair()
            current = _relative_point(point, current) if command == "m" else point
            start = current
            points.append(current)
            command = "l" if command == "m" else "L"
            prev_cubic_control = None
            prev_quadratic_control = None
            continue

        if command in "Ll":
            point = read_pair()
            current = _relative_point(point, current) if command == "l" else point
            points.append(current)
            prev_cubic_control = None
            prev_quadratic_control = None
            continue

        if command in "Hh":
            x = read_number()
            current = (current[0] + x, current[1]) if command == "h" else (x, current[1])
            points.append(current)
            prev_cubic_control = None
            prev_quadratic_control = None
            continue

        if command in "Vv":
            y = read_number()
            current = (current[0], current[1] + y) if command == "v" else (current[0], y)
            points.append(current)
            prev_cubic_control = None
            prev_quadratic_control = None
            continue

        if command in "Cc":
            c1 = read_pair()
            c2 = read_pair()
            end = read_pair()
            if command == "c":
                c1 = _relative_point(c1, current)
                c2 = _relative_point(c2, current)
                end = _relative_point(end, current)
            points.extend(_sample_cubic(current, c1, c2, end))
            current = end
            prev_cubic_control = c2
            prev_quadratic_control = None
            continue

        if command in "Ss":
            c2 = read_pair()
            end = read_pair()
            if command == "s":
                c2 = _relative_point(c2, current)
                end = _relative_point(end, current)
            c1 = _reflect_point(prev_cubic_control, current)
            points.extend(_sample_cubic(current, c1, c2, end))
            current = end
            prev_cubic_control = c2
            prev_quadratic_control = None
            continue

        if command in "Qq":
            c = read_pair()
            end = read_pair()
            if command == "q":
                c = _relative_point(c, current)
                end = _relative_point(end, current)
            points.extend(_sample_quadratic(current, c, end))
            current = end
            prev_cubic_control = None
            prev_quadratic_control = c
            continue

        if command in "Tt":
            end = read_pair()
            if command == "t":
                end = _relative_point(end, current)
            c = _reflect_point(prev_quadratic_control, current)
            points.extend(_sample_quadratic(current, c, end))
            current = end
            prev_cubic_control = None
            prev_quadratic_control = c
            continue

        raise ValueError(f"unsupported path command {command!r}")

    return _dedupe_points(points)


def _sample_cubic(
    start: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    return [_cubic_point(start, c1, c2, end, step / SAMPLES_PER_SEGMENT) for step in range(1, SAMPLES_PER_SEGMENT + 1)]


def _cubic_point(
    start: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    end: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u**3 * start[0] + 3 * u**2 * t * c1[0] + 3 * u * t**2 * c2[0] + t**3 * end[0],
        u**3 * start[1] + 3 * u**2 * t * c1[1] + 3 * u * t**2 * c2[1] + t**3 * end[1],
    )


def _sample_quadratic(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    return [
        _quadratic_point(start, control, end, step / SAMPLES_PER_SEGMENT)
        for step in range(1, SAMPLES_PER_SEGMENT + 1)
    ]


def _quadratic_point(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u**2 * start[0] + 2 * u * t * control[0] + t**2 * end[0],
        u**2 * start[1] + 2 * u * t * control[1] + t**2 * end[1],
    )


def _relative_point(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    return (origin[0] + point[0], origin[1] + point[1])


def _reflect_point(point: tuple[float, float] | None, center: tuple[float, float]) -> tuple[float, float]:
    if point is None:
        return center
    return (2 * center[0] - point[0], 2 * center[1] - point[1])


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or _distance(point, deduped[-1]) > 1e-9:
            deduped.append(point)
    return deduped


def _normalize_strokes_to_view_box(
    strokes: list[list[tuple[float, float]]],
    view_box: tuple[float, float, float, float],
) -> list[list[tuple[float, float]]]:
    if not strokes:
        return []

    min_x, min_y, width, height = view_box
    size = max(width, height, 1e-9)
    offset_x = (size - width) / 2.0
    offset_y = (size - height) / 2.0

    return [
        [
            (
                _clamp_unit((x - min_x + offset_x) / size),
                _clamp_unit((y - min_y + offset_y) / size),
            )
            for x, y in stroke
        ]
        for stroke in strokes
    ]


def _view_box(root: ET.Element) -> tuple[float, float, float, float]:
    raw = str(root.attrib.get("viewBox", "")).strip()
    if raw:
        values = [float(value) for value in re.split(r"[,\s]+", raw) if value]
        if len(values) == 4 and values[2] > 0.0 and values[3] > 0.0:
            return (values[0], values[1], values[2], values[3])

    width = float(str(root.attrib.get("width", "109")).removesuffix("px"))
    height = float(str(root.attrib.get("height", "109")).removesuffix("px"))
    return (0.0, 0.0, width, height)


def _bbox_from_strokes(strokes: list[list[tuple[float, float]]]) -> tuple[float, float, float, float]:
    xs = [x for stroke in strokes for x, _ in stroke]
    ys = [y for stroke in strokes for _, y in stroke]
    return (min(xs), min(ys), max(xs), max(ys))


def _find_stroke_paths_group(root: ET.Element) -> ET.Element:
    for element in root.iter():
        if _local_name(element.tag) == "g" and str(element.get("id", "")).startswith("kvg:StrokePaths_"):
            return element
    raise ValueError("KanjiVG stroke paths group not found")


def _attribute(element: ET.Element, name: str, default: str = "") -> str:
    for key, value in element.attrib.items():
        if key == name or key.endswith(f"}}{name}"):
            return str(value)
    return default


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.02), 0.98)


def _round_unit(value: float) -> float:
    return round(value, 6)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _classify_script(char: str) -> str:
    code = ord(char)
    if 0x3040 <= code <= 0x309F:
        return "hiragana"
    if 0x30A0 <= code <= 0x30FF:
        return "katakana"
    if "0" <= char <= "9":
        return "digit"
    if ("A" <= char <= "Z") or ("a" <= char <= "z"):
        return "latin"
    if char in "。、,.!?！ー・「」『』()[]+-=*/:;":
        return "symbol"
    return "kanji"


def _display_scale(literal: str, *, script_group: str) -> float:
    # 小書きかな・長音記号・全角句読点(。、・)は KanjiVG が em-box 内に正しいサイズ・
    # 位置で描いているため、追加の縮小は行わず KanjiVG 幾何をそのまま使う。
    if literal in "。、・":
        return 1.0
    if literal in "！？!?":
        return 0.60
    if script_group == "latin":
        return 0.92
    if script_group == "digit":
        return 0.88
    if script_group == "symbol":
        return 0.48
    return 1.0


def _advance_ratio(literal: str, *, script_group: str) -> float:
    # 小書きかな・長音記号も全角1マスを占めるため、通常のかなと同じ送り幅にする。
    # 全角句読点(。、・)は KanjiVG 幾何が下寄り/中央の小グリフなので、詰まりすぎない
    # 中庸の送り幅にする。
    if literal in "。、・":
        return 0.5
    if literal in "！？!?":
        return 0.44
    if script_group in {"hiragana", "katakana"}:
        return 0.9
    if script_group == "latin":
        return 0.70
    if script_group == "digit":
        return 0.74
    if script_group == "symbol":
        return 0.36
    return 0.9


def _terminal_for(stroke_type: str) -> str:
    parts = tuple(part.strip() for part in stroke_type.split("/") if part.strip()) or (stroke_type,)
    if any(part in {"hidari", "migi", "㇀", "㇁", "㇂", "㇒", "㇓", "㇏", "㇇"} for part in parts):
        return "harai"
    if any(part in {"hane", "㇆", "㇈", "㇉", "㇙", "㇛", "㇜", "㇟"} for part in parts):
        return "hane"
    if any(part in {"ten", "yoko", "tate", "ori", "㇔", "㇐", "㇑", "㇕", "㇖", "㇗"} for part in parts):
        return "tome"
    return "none"


if __name__ == "__main__":
    main()

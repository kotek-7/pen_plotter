from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from character_dictionary.models import CharacterTemplate, StrokeTemplate
from character_dictionary.terminal import map_stroke_type_to_terminal


KANJIVG_BASE_URL = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji"
KANJIVG_NAMESPACE = "http://kanjivg.tagaini.net"
KANJIVG_LICENSE = "CC BY-SA 3.0"
KANJIVG_SOURCE = "kanjivg"
KANJIVG_SAMPLES_PER_SEGMENT = 10

_TOKEN_RE = re.compile(r"[MmCcSsZz]|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def kanjivg_file_name(literal: str) -> str:
    return f"{ord(literal):05x}.svg"


def kanjivg_raw_url(literal: str) -> str:
    return f"{KANJIVG_BASE_URL}/{kanjivg_file_name(literal)}"


def download_kanjivg_svg_text(literal: str) -> str:
    with urllib.request.urlopen(kanjivg_raw_url(literal), timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8")


def build_kanjivg_template(literal: str, svg_text: str | None = None) -> CharacterTemplate:
    svg_text = svg_text if svg_text is not None else download_kanjivg_svg_text(literal)
    strokes, bbox = _parse_svg_template(literal, svg_text)
    if not strokes:
        raise ValueError(f"no KanjiVG strokes found for {literal!r}")
    return CharacterTemplate(
        char_id=f"U+{ord(literal):04X}",
        literal=literal,
        source=KANJIVG_SOURCE,
        license=KANJIVG_LICENSE,
        bbox=bbox,
        strokes=tuple(strokes),
    )


def build_kanjivg_asset(literals: list[str] | tuple[str, ...]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for literal in literals:
        try:
            template = build_kanjivg_template(literal)
        except Exception:
            continue
        entries.append(template_to_asset_entry(template))
    return {
        "schema_version": 1,
        "source": KANJIVG_SOURCE,
        "license": KANJIVG_LICENSE,
        "character_count": len(entries),
        "characters": entries,
    }


def template_to_asset_entry(template: CharacterTemplate) -> dict[str, Any]:
    data = asdict(template)
    data["bbox"] = list(template.bbox)
    data["strokes"] = [stroke_to_asset_entry(stroke) for stroke in template.strokes]
    return data


def stroke_to_asset_entry(stroke: StrokeTemplate) -> dict[str, Any]:
    data = asdict(stroke)
    data["skeleton_points"] = [list(point) for point in stroke.skeleton_points]
    return data


def dump_kanjivg_asset(path: Path, literals: list[str] | tuple[str, ...]) -> None:
    asset = build_kanjivg_asset(literals)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asset, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_kanjivg_asset(path: Path) -> dict[str, CharacterTemplate]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    templates: dict[str, CharacterTemplate] = {}
    for item in payload.get("characters", []):
        strokes = tuple(
            StrokeTemplate(
                stroke_id=int(stroke["stroke_id"]),
                order=int(stroke["order"]),
                stroke_type=str(stroke["stroke_type"]),
                skeleton_points=tuple((float(x), float(y)) for x, y in stroke["skeleton_points"]),
                terminal=str(stroke["terminal"]),
                path=str(stroke.get("path", "")),
                confidence=float(stroke.get("confidence", 1.0)),
            )
            for stroke in item.get("strokes", [])
        )
        template = CharacterTemplate(
            char_id=str(item["char_id"]),
            literal=str(item["literal"]),
            source=str(item["source"]),
            license=str(item["license"]),
            bbox=tuple(float(value) for value in item["bbox"]),
            strokes=strokes,
        )
        templates[template.literal] = template
    return templates


def _parse_svg_template(literal: str, svg_text: str) -> tuple[list[StrokeTemplate], tuple[float, float, float, float]]:
    root = ET.fromstring(svg_text)
    stroke_paths_group = _find_stroke_paths_group(root)
    path_elements = [
        element
        for element in stroke_paths_group.iter()
        if _local_name(element.tag) == "path"
    ]

    sampled_strokes: list[np.ndarray] = []
    stroke_templates: list[StrokeTemplate] = []
    for index, path_element in enumerate(path_elements, start=1):
        d = path_element.get("d", "").strip()
        if not d:
            continue
        sampled_points = _sample_path(d)
        if len(sampled_points) < 2:
            continue
        sampled_strokes.append(np.array(sampled_points, dtype=float))
        raw_type = _attribute(path_element, "type", default="")
        normalized_type = _normalize_stroke_type(raw_type)
        stroke_templates.append(
            StrokeTemplate(
                stroke_id=index,
                order=index,
                stroke_type=normalized_type,
                skeleton_points=(),
                terminal=map_stroke_type_to_terminal(raw_type or normalized_type),
                path=d,
                confidence=1.0,
            )
        )

    normalized_strokes = _normalize_strokes_to_unit_square(sampled_strokes)
    if len(normalized_strokes) != len(stroke_templates):
        raise ValueError(f"stroke count mismatch for {literal!r}")

    strokes: list[StrokeTemplate] = []
    for template, points in zip(stroke_templates, normalized_strokes, strict=False):
        strokes.append(
            StrokeTemplate(
                stroke_id=template.stroke_id,
                order=template.order,
                stroke_type=template.stroke_type,
                skeleton_points=points,
                terminal=template.terminal,
                path=template.path,
                confidence=template.confidence,
            )
        )

    bbox = _bbox_from_strokes(normalized_strokes)
    return strokes, bbox


def _sample_path(d: str) -> list[tuple[float, float]]:
    tokens = _TOKEN_RE.findall(d)
    if not tokens:
        return []

    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_control: tuple[float, float] | None = None
    command: str | None = None
    index = 0

    def _read_pair() -> tuple[float, float]:
        nonlocal index
        x = float(tokens[index])
        y = float(tokens[index + 1])
        index += 2
        return (x, y)

    while index < len(tokens):
        token = tokens[index]
        if token in "MmCcSsZz":
            command = token
            index += 1
            if token in "Zz":
                current = start
                prev_control = None
                continue
            if token in "Mm":
                point = _read_pair()
                current = _relative_point(point, current) if token == "m" else point
                start = current
                points.append(current)
                prev_control = None
                command = None
            continue

        if command is None:
            raise ValueError(f"path data missing command in {d!r}")

        if command in "Mm":
            point = _read_pair()
            current = _relative_point(point, current) if command == "m" else point
            start = current
            points.append(current)
            prev_control = None
            command = None
            continue

        if command in "Cc":
            c1 = _read_pair()
            c2 = _read_pair()
            end = _read_pair()
            if command == "c":
                c1 = _relative_point(c1, current)
                c2 = _relative_point(c2, current)
                end = _relative_point(end, current)
            points.extend(_sample_cubic(current, c1, c2, end))
            current = end
            prev_control = c2
            continue

        if command in "Ss":
            c2 = _read_pair()
            end = _read_pair()
            if command == "s":
                c2 = _relative_point(c2, current)
                end = _relative_point(end, current)
            c1 = _reflect_point(prev_control, current)
            points.extend(_sample_cubic(current, c1, c2, end))
            current = end
            prev_control = c2
            continue

        raise ValueError(f"unsupported path command {command!r}")

    return _dedupe_points(points)


def _sample_cubic(
    start: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    for step in range(1, KANJIVG_SAMPLES_PER_SEGMENT + 1):
        t = step / KANJIVG_SAMPLES_PER_SEGMENT
        samples.append(_cubic_point(start, c1, c2, end, t))
    return samples


def _cubic_point(
    start: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    end: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    x = (
        u**3 * start[0]
        + 3 * u**2 * t * c1[0]
        + 3 * u * t**2 * c2[0]
        + t**3 * end[0]
    )
    y = (
        u**3 * start[1]
        + 3 * u**2 * t * c1[1]
        + 3 * u * t**2 * c2[1]
        + t**3 * end[1]
    )
    return (x, y)


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


def _normalize_strokes_to_unit_square(
    strokes: list[np.ndarray],
) -> list[tuple[tuple[float, float], ...]]:
    if not strokes:
        return []

    all_points = np.concatenate(strokes, axis=0)
    min_x = float(np.min(all_points[:, 0]))
    max_x = float(np.max(all_points[:, 0]))
    min_y = float(np.min(all_points[:, 1]))
    max_y = float(np.max(all_points[:, 1]))
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    size = max(width, height, 1e-9)
    offset_x = (size - width) / 2.0
    offset_y = (size - height) / 2.0

    normalized: list[tuple[tuple[float, float], ...]] = []
    for stroke in strokes:
        normalized.append(
            tuple(
                (
                    _clamp_unit((float(x) - min_x + offset_x) / size),
                    _clamp_unit((float(y) - min_y + offset_y) / size),
                )
                for x, y in stroke
            )
        )
    return normalized


def _bbox_from_strokes(strokes: list[tuple[tuple[float, float], ...]]) -> tuple[float, float, float, float]:
    if not strokes:
        return (0.0, 0.0, 1.0, 1.0)
    xs = [x for stroke in strokes for x, _ in stroke]
    ys = [y for stroke in strokes for _, y in stroke]
    return (min(xs), min(ys), max(xs), max(ys))


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.02), 0.98)


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


def _normalize_stroke_type(raw_type: str) -> str:
    if not raw_type:
        return "none"
    first = raw_type.split("/", maxsplit=1)[0]
    return first


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))

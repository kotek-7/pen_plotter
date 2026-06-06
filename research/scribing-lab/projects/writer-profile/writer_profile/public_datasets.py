from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from writer_profile.prior import HandwritingPointRecord

HF_HANDWRITING_V1_DATASET_ID = "finnbusse/handwriting-v1"
HF_HANDWRITING_V1_LICENSE_SCOPE = "MIT"
HF_HANDWRITING_V1_SOURCE = "finnbusse/handwriting-v1"


def convert_finnbusse_handwriting_v1_entry(
    entry: dict[str, Any],
    *,
    source: str = HF_HANDWRITING_V1_SOURCE,
    license_scope: str = HF_HANDWRITING_V1_LICENSE_SCOPE,
    writer_id_mode: str = "session_id",
    file_hint: str = "",
) -> list[HandwritingPointRecord]:
    sample_id = str(entry["id"])
    text = str(entry["text"])
    scale = float(entry["scale"])
    if scale <= 0.0:
        raise ValueError(f"invalid scale for sample {sample_id}: {scale}")

    writer_id = _resolve_writer_id(entry, writer_id_mode=writer_id_mode, file_hint=file_hint)
    session_speed_mm_s = _session_speed_mm_s(entry, writer_id=writer_id, text=text)
    x_mm = 0.0
    y_mm = 0.0
    t_ms = 0
    points: list[HandwritingPointRecord] = []
    raw_points = list(entry["points"])
    for index, raw_point in enumerate(raw_points):
        dx_mm = float(raw_point["dx"]) / scale
        dy_mm = float(raw_point["dy"]) / scale
        x_mm += dx_mm
        y_mm += dy_mm
        if index > 0:
            distance_mm = (dx_mm**2 + dy_mm**2) ** 0.5
            t_ms += max(4, int(round(distance_mm / max(session_speed_mm_s, 1e-6) * 1000.0)))
        points.append(
            HandwritingPointRecord(
                sample_id=sample_id,
                writer_id=writer_id,
                char_or_text=text,
                x_mm=round(x_mm, 4),
                y_mm=round(y_mm, 4),
                t_ms=t_ms,
                pen_state=1,
                pressure_optional=None,
                source=source,
                license_scope=license_scope,
            )
        )
        if int(raw_point.get("eos", 0)) == 1:
            t_ms += _stroke_pause_ms(text=text, writer_id=writer_id, index=index)
            points.append(
                HandwritingPointRecord(
                    sample_id=sample_id,
                    writer_id=writer_id,
                    char_or_text=text,
                    x_mm=round(x_mm, 4),
                    y_mm=round(y_mm, 4),
                    t_ms=t_ms,
                    pen_state=0,
                    pressure_optional=None,
                    source=source,
                    license_scope=license_scope,
                )
            )
    return points


def convert_finnbusse_handwriting_v1_jsonl(
    input_path: str | Path,
    output_path: str | Path,
    *,
    source: str = HF_HANDWRITING_V1_SOURCE,
    license_scope: str = HF_HANDWRITING_V1_LICENSE_SCOPE,
    writer_id_mode: str = "session_id",
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    stats = {
        "source": source,
        "license_scope": license_scope,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "raw_sample_count": 0,
        "canonical_point_count": 0,
        "writer_ids": set(),
        "sample_ids": set(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8") as input_stream, output_path.open(
        "w", encoding="utf-8"
    ) as output_stream:
        for line_no, raw in enumerate(input_stream, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid handwriting JSONL line {line_no}: {exc}") from exc
            converted = convert_finnbusse_handwriting_v1_entry(
                entry,
                source=source,
                license_scope=license_scope,
                writer_id_mode=writer_id_mode,
                file_hint=input_path.stem,
            )
            stats["raw_sample_count"] += 1
            if converted:
                stats["sample_ids"].add(converted[0].sample_id)
                stats["writer_ids"].add(converted[0].writer_id)
            for point in converted:
                output_stream.write(json.dumps(point.to_dict(), ensure_ascii=False))
                output_stream.write("\n")
                stats["canonical_point_count"] += 1
    stats["writer_ids"] = sorted(stats["writer_ids"])
    stats["sample_ids"] = sorted(stats["sample_ids"])
    stats["writer_count"] = len(stats["writer_ids"])
    stats["sample_count"] = len(stats["sample_ids"])
    return stats


def download_finnbusse_handwriting_v1_jsonl_files(
    *,
    dataset_id: str = HF_HANDWRITING_V1_DATASET_ID,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    metadata = _download_json(
        f"https://huggingface.co/api/datasets/{dataset_id}",
        timeout=timeout,
    )
    siblings = metadata.get("siblings", [])
    files: list[dict[str, Any]] = []
    for sibling in siblings:
        filename = str(sibling.get("rfilename", ""))
        if filename.startswith("data/") and filename.endswith(".jsonl"):
            files.append(
                {
                    "filename": filename,
                    "url": f"https://huggingface.co/datasets/{dataset_id}/resolve/main/{filename}",
                }
            )
    return sorted(files, key=lambda item: item["filename"])


def download_and_convert_finnbusse_handwriting_v1(
    output_path: str | Path,
    *,
    dataset_id: str = HF_HANDWRITING_V1_DATASET_ID,
    source: str = HF_HANDWRITING_V1_SOURCE,
    license_scope: str = HF_HANDWRITING_V1_LICENSE_SCOPE,
    writer_id_mode: str = "session_id",
    timeout: float = 60.0,
) -> dict[str, Any]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = download_finnbusse_handwriting_v1_jsonl_files(dataset_id=dataset_id, timeout=timeout)
    stats = {
        "dataset_id": dataset_id,
        "source": source,
        "license_scope": license_scope,
        "writer_id_mode": writer_id_mode,
        "file_count": len(files),
        "raw_sample_count": 0,
        "canonical_point_count": 0,
        "writer_ids": set(),
        "sample_ids": set(),
        "files": [],
    }
    with output_path.open("w", encoding="utf-8") as output_stream:
        for file_info in files:
            raw_text = _download_text(file_info["url"], timeout=timeout)
            file_stats = {
                "filename": file_info["filename"],
                "raw_sample_count": 0,
                "canonical_point_count": 0,
                "writer_ids": set(),
            }
            for line_no, raw in enumerate(raw_text.splitlines(), start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid handwriting JSONL line {line_no} in {file_info['filename']}: {exc}"
                    ) from exc
                converted = convert_finnbusse_handwriting_v1_entry(
                    entry,
                    source=source,
                    license_scope=license_scope,
                    writer_id_mode=writer_id_mode,
                    file_hint=Path(file_info["filename"]).stem,
                )
                file_stats["raw_sample_count"] += 1
                stats["raw_sample_count"] += 1
                if converted:
                    stats["sample_ids"].add(converted[0].sample_id)
                    stats["writer_ids"].add(converted[0].writer_id)
                    file_stats["writer_ids"].add(converted[0].writer_id)
                for point in converted:
                    output_stream.write(json.dumps(point.to_dict(), ensure_ascii=False))
                    output_stream.write("\n")
                    file_stats["canonical_point_count"] += 1
                    stats["canonical_point_count"] += 1
            file_stats["writer_ids"] = sorted(file_stats["writer_ids"])
            stats["files"].append(file_stats)
    stats["writer_ids"] = sorted(stats["writer_ids"])
    stats["sample_ids"] = sorted(stats["sample_ids"])
    stats["writer_count"] = len(stats["writer_ids"])
    stats["sample_count"] = len(stats["sample_ids"])
    return stats


def _resolve_writer_id(
    entry: dict[str, Any],
    *,
    writer_id_mode: str,
    file_hint: str,
) -> str:
    session_id = str(entry.get("session_id", "")).strip()
    if writer_id_mode == "session_id":
        if session_id:
            return f"session:{session_id}"
        if file_hint:
            return f"file:{file_hint}"
        return "session:unknown"
    if writer_id_mode == "file_stem":
        if file_hint:
            return f"file:{file_hint}"
        if session_id:
            return f"session:{session_id}"
        return "file:unknown"
    raise ValueError(f"unsupported writer_id_mode: {writer_id_mode}")


def _session_speed_mm_s(entry: dict[str, Any], *, writer_id: str, text: str) -> float:
    payload = json.dumps(
        {
            "writer_id": writer_id,
            "text": text,
            "scale": float(entry.get("scale", 1.0)),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    base_speed = 24.0 + (int(digest[:4], 16) % 1400) / 100.0
    text_adjustment = min(len(text), 18) * 0.18
    return round(base_speed + text_adjustment, 4)


def _stroke_pause_ms(*, text: str, writer_id: str, index: int) -> int:
    digest = hashlib.sha256(f"{writer_id}:{text}:{index}".encode("utf-8")).hexdigest()
    base_pause = 18 + (int(digest[:2], 16) % 18)
    text_adjustment = min(len(text), 18) // 3
    return base_pause + text_adjustment


def _download_json(url: str, *, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download JSON from {url}: {exc}") from exc


def _download_text(url: str, *, timeout: float) -> str:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download text from {url}: {exc}") from exc


def summarize_finnbusse_handwriting_v1_conversion(files: Iterable[dict[str, Any]]) -> dict[str, Any]:
    file_list = list(files)
    writer_ids = sorted(
        {
            str(writer_id)
            for file_info in file_list
            for writer_id in file_info.get("writer_ids", [])
        }
    )
    return {
        "dataset_id": HF_HANDWRITING_V1_DATASET_ID,
        "file_count": len(file_list),
        "writer_count": len(writer_ids),
        "writer_ids": writer_ids,
        "raw_sample_count": sum(int(file_info.get("raw_sample_count", 0)) for file_info in file_list),
        "canonical_point_count": sum(
            int(file_info.get("canonical_point_count", 0)) for file_info in file_list
        ),
    }

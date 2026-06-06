from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from writer_profile.models import WriterProfileParameters
from writer_profile.registry import get_profile


@dataclass(frozen=True)
class HandwritingPointRecord:
    sample_id: str
    writer_id: str
    char_or_text: str
    x_mm: float
    y_mm: float
    t_ms: int
    pen_state: int
    pressure_optional: float | None
    source: str
    license_scope: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandwritingPointRecord:
        return cls(
            sample_id=str(data["sample_id"]),
            writer_id=str(data["writer_id"]),
            char_or_text=str(data["char_or_text"]),
            x_mm=float(data["x_mm"]),
            y_mm=float(data["y_mm"]),
            t_ms=int(data["t_ms"]),
            pen_state=int(data["pen_state"]),
            pressure_optional=(
                None if data.get("pressure_optional") in {None, ""} else float(data["pressure_optional"])
            ),
            source=str(data["source"]),
            license_scope=str(data["license_scope"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "writer_id": self.writer_id,
            "char_or_text": self.char_or_text,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "t_ms": self.t_ms,
            "pen_state": self.pen_state,
            "pressure_optional": self.pressure_optional,
            "source": self.source,
            "license_scope": self.license_scope,
        }


@dataclass(frozen=True)
class HandwritingSample:
    sample_id: str
    writer_id: str
    char_or_text: str
    source: str
    license_scope: str
    points: tuple[HandwritingPointRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "writer_id": self.writer_id,
            "char_or_text": self.char_or_text,
            "source": self.source,
            "license_scope": self.license_scope,
            "point_count": len(self.points),
            "points": [point.to_dict() for point in self.points],
        }


def load_handwriting_points_jsonl(path: str | Path) -> list[HandwritingPointRecord]:
    path = Path(path)
    records: list[HandwritingPointRecord] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(HandwritingPointRecord.from_dict(json.loads(line)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid handwriting JSONL line {line_no}: {exc}") from exc
    return records


def group_handwriting_samples(records: list[HandwritingPointRecord]) -> list[HandwritingSample]:
    grouped: dict[str, list[HandwritingPointRecord]] = defaultdict(list)
    for record in records:
        grouped[record.sample_id].append(record)

    samples: list[HandwritingSample] = []
    for sample_id in sorted(grouped):
        points = sorted(grouped[sample_id], key=lambda item: (item.t_ms, item.pen_state, item.x_mm, item.y_mm))
        if not points:
            continue
        writer_id = points[0].writer_id
        char_or_text = points[0].char_or_text
        source = points[0].source
        license_scope = points[0].license_scope
        for point in points[1:]:
            if point.writer_id != writer_id or point.char_or_text != char_or_text:
                raise ValueError(f"sample {sample_id} mixes writer or text identifiers")
        samples.append(
            HandwritingSample(
                sample_id=sample_id,
                writer_id=writer_id,
                char_or_text=char_or_text,
                source=source,
                license_scope=license_scope,
                points=tuple(points),
            )
        )
    return samples


def summarize_handwriting_samples(
    records: list[HandwritingPointRecord],
) -> dict[str, Any]:
    samples = group_handwriting_samples(records)
    if not samples:
        return {
            "sample_count": 0,
            "writer_count": 0,
            "text_count": 0,
            "point_count": 0,
            "stroke_count": 0,
            "mean_speed_mm_s": 0.0,
            "speed_cv": 0.0,
            "spacing_mean_mm": 0.0,
            "spacing_cv": 0.0,
            "slant_deg": 0.0,
            "baseline_drift_mm": 0.0,
            "tremor_mm": 0.0,
            "pressure_mean": 0.0,
            "pressure_cv": 0.0,
            "terminal_pressure_mean": 0.0,
            "terminal_pressure_cv": 0.0,
            "balanced_sample_count": 0,
            "balanced_writer_count": 0,
            "balanced_mean_speed_mm_s": 0.0,
            "balanced_speed_cv": 0.0,
            "balanced_spacing_mean_mm": 0.0,
            "balanced_spacing_cv": 0.0,
            "balanced_slant_deg": 0.0,
            "balanced_baseline_drift_mm": 0.0,
            "balanced_tremor_mm": 0.0,
            "balanced_pressure_mean": 0.0,
            "balanced_pressure_cv": 0.0,
            "balanced_terminal_pressure_mean": 0.0,
            "balanced_terminal_pressure_cv": 0.0,
            "writer_sample_counts": {},
            "writer_summaries": [],
            "source_counts": {},
            "license_scope_counts": {},
            "sample_summaries": [],
        }

    writer_ids = sorted({sample.writer_id for sample in samples})
    texts = sorted({sample.char_or_text for sample in samples})
    source_counts: dict[str, int] = defaultdict(int)
    license_scope_counts: dict[str, int] = defaultdict(int)
    speeds: list[float] = []
    spacings: list[float] = []
    slants: list[float] = []
    drifts: list[float] = []
    tremors: list[float] = []
    pressures: list[float] = []
    terminal_pressures: list[float] = []
    stroke_count = 0

    sample_summaries: list[dict[str, Any]] = []
    writer_metric_buckets: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    writer_sample_counts: dict[str, int] = defaultdict(int)
    for sample in samples:
        writer_sample_counts[sample.writer_id] += 1
        source_counts[sample.source] += 1
        license_scope_counts[sample.license_scope] += 1
        segments = _pen_down_segments(sample.points)
        stroke_count += len(segments)
        sample_speed = _sample_mean_speed(sample.points, segments)
        if sample_speed is not None:
            speeds.append(sample_speed)
        sample_spacing = _sample_mean_spacing(segments)
        if sample_spacing is not None:
            spacings.append(sample_spacing)
        sample_slant = _sample_slant_deg(sample.points)
        if sample_slant is not None:
            slants.append(sample_slant)
        sample_drift = _sample_baseline_drift_mm(segments)
        if sample_drift is not None:
            drifts.append(sample_drift)
        sample_tremor = _sample_tremor_mm(sample.points, segments)
        if sample_tremor is not None:
            tremors.append(sample_tremor)
        sample_pressures = [point.pressure_optional for point in sample.points if point.pressure_optional is not None]
        pressures.extend(float(value) for value in sample_pressures)
        terminal_pressures.extend(
            float(segment[-1].pressure_optional)
            for segment in segments
            if segment and segment[-1].pressure_optional is not None
        )
        sample_summaries.append(
            {
                "sample_id": sample.sample_id,
                "writer_id": sample.writer_id,
                "char_or_text": sample.char_or_text,
                "point_count": len(sample.points),
                "stroke_count": len(segments),
                "mean_speed_mm_s": round(sample_speed or 0.0, 4),
                "spacing_mean_mm": round(sample_spacing or 0.0, 4),
                "slant_deg": round(sample_slant or 0.0, 4),
                "baseline_drift_mm": round(sample_drift or 0.0, 4),
                "tremor_mm": round(sample_tremor or 0.0, 4),
            }
        )
        if sample_speed is not None:
            writer_metric_buckets[sample.writer_id]["mean_speed_mm_s"].append(sample_speed)
        if sample_spacing is not None:
            writer_metric_buckets[sample.writer_id]["spacing_mean_mm"].append(sample_spacing)
        if sample_slant is not None:
            writer_metric_buckets[sample.writer_id]["slant_deg"].append(sample_slant)
        if sample_drift is not None:
            writer_metric_buckets[sample.writer_id]["baseline_drift_mm"].append(sample_drift)
        if sample_tremor is not None:
            writer_metric_buckets[sample.writer_id]["tremor_mm"].append(sample_tremor)
        for value in sample_pressures:
            writer_metric_buckets[sample.writer_id]["pressure_mean"].append(float(value))
        for value in (
            float(segment[-1].pressure_optional)
            for segment in segments
            if segment and segment[-1].pressure_optional is not None
        ):
            writer_metric_buckets[sample.writer_id]["terminal_pressure_mean"].append(value)

    writer_summaries: list[dict[str, Any]] = []
    balanced_speed_values: list[float] = []
    balanced_spacing_values: list[float] = []
    balanced_slant_values: list[float] = []
    balanced_drift_values: list[float] = []
    balanced_tremor_values: list[float] = []
    balanced_pressure_values: list[float] = []
    balanced_terminal_pressure_values: list[float] = []
    for writer_id in sorted(writer_metric_buckets):
        buckets = writer_metric_buckets[writer_id]
        sample_count = writer_sample_counts[writer_id]
        writer_summary = {
            "writer_id": writer_id,
            "sample_count": sample_count,
            "mean_speed_mm_s": _safe_mean(buckets["mean_speed_mm_s"]),
            "speed_cv": _safe_cv(buckets["mean_speed_mm_s"]),
            "spacing_mean_mm": _safe_mean(buckets["spacing_mean_mm"]),
            "spacing_cv": _safe_cv(buckets["spacing_mean_mm"]),
            "slant_deg": _safe_mean(buckets["slant_deg"]),
            "baseline_drift_mm": _safe_mean(buckets["baseline_drift_mm"]),
            "tremor_mm": _safe_mean(buckets["tremor_mm"]),
            "pressure_mean": _safe_mean(buckets["pressure_mean"]),
            "pressure_cv": _safe_cv(buckets["pressure_mean"]),
            "terminal_pressure_mean": _safe_mean(buckets["terminal_pressure_mean"]),
            "terminal_pressure_cv": _safe_cv(buckets["terminal_pressure_mean"]),
        }
        writer_summaries.append(writer_summary)
        balanced_speed_values.append(float(writer_summary["mean_speed_mm_s"]))
        balanced_spacing_values.append(float(writer_summary["spacing_mean_mm"]))
        balanced_slant_values.append(float(writer_summary["slant_deg"]))
        balanced_drift_values.append(float(writer_summary["baseline_drift_mm"]))
        balanced_tremor_values.append(float(writer_summary["tremor_mm"]))
        balanced_pressure_values.append(float(writer_summary["pressure_mean"]))
        balanced_terminal_pressure_values.append(float(writer_summary["terminal_pressure_mean"]))

    balanced_writer_count = len(writer_summaries)
    balanced_sample_count = sum(writer_sample_counts.values())
    dominant_writer_sample_count = max(writer_sample_counts.values(), default=0)
    dominant_writer_sample_ratio = (
        round(dominant_writer_sample_count / balanced_sample_count, 4)
        if balanced_sample_count
        else 0.0
    )

    summary = {
        "sample_count": len(samples),
        "writer_count": len(writer_ids),
        "text_count": len(texts),
        "point_count": sum(len(sample.points) for sample in samples),
        "stroke_count": stroke_count,
        "mean_speed_mm_s": _safe_mean(speeds),
        "speed_cv": _safe_cv(speeds),
        "spacing_mean_mm": _safe_mean(spacings),
        "spacing_cv": _safe_cv(spacings),
        "slant_deg": _safe_mean(slants),
        "baseline_drift_mm": _safe_mean(drifts),
        "tremor_mm": _safe_mean(tremors),
        "pressure_mean": _safe_mean(pressures),
        "pressure_cv": _safe_cv(pressures),
        "terminal_pressure_mean": _safe_mean(terminal_pressures),
        "terminal_pressure_cv": _safe_cv(terminal_pressures),
        "balanced_sample_count": balanced_sample_count,
        "balanced_writer_count": balanced_writer_count,
        "balanced_mean_speed_mm_s": _safe_mean(balanced_speed_values),
        "balanced_speed_cv": _safe_cv(balanced_speed_values),
        "balanced_spacing_mean_mm": _safe_mean(balanced_spacing_values),
        "balanced_spacing_cv": _safe_cv(balanced_spacing_values),
        "balanced_slant_deg": _safe_mean(balanced_slant_values),
        "balanced_baseline_drift_mm": _safe_mean(balanced_drift_values),
        "balanced_tremor_mm": _safe_mean(balanced_tremor_values),
        "balanced_pressure_mean": _safe_mean(balanced_pressure_values),
        "balanced_pressure_cv": _safe_cv(balanced_pressure_values),
        "balanced_terminal_pressure_mean": _safe_mean(balanced_terminal_pressure_values),
        "balanced_terminal_pressure_cv": _safe_cv(balanced_terminal_pressure_values),
        "dominant_writer_sample_ratio": dominant_writer_sample_ratio,
        "writer_sample_counts": dict(sorted(writer_sample_counts.items())),
        "writer_summaries": writer_summaries,
        "source_counts": dict(sorted(source_counts.items())),
        "license_scope_counts": dict(sorted(license_scope_counts.items())),
        "sample_summaries": sample_summaries,
    }
    return summary


def estimate_writer_profile_from_points(
    records: list[HandwritingPointRecord],
    *,
    base_profile_id: str = "baseline-neat",
    profile_id: str | None = None,
) -> dict[str, Any]:
    base_profile = get_profile(base_profile_id)
    summary = summarize_handwriting_samples(records)
    params = _profile_params_from_summary(summary, base_profile.params)
    derived_profile = replace(
        base_profile,
        profile_id=profile_id or _derived_profile_id(base_profile.profile_id, summary),
        version=base_profile.version + 1,
        source="data-driven",
        allowed_use="research-prior",
        parent_profile=base_profile.profile_id,
        created_from_experiment=f"handwriting-prior:{summary['sample_count']}",
        params=params,
        notes=_prior_notes(base_profile.notes, summary),
    )
    return {
        "base_profile_id": base_profile_id,
        "profile": derived_profile,
        "summary": summary,
        "source": "data-driven",
    }


def estimate_writer_profile_from_jsonl(
    path: str | Path,
    *,
    base_profile_id: str = "baseline-neat",
    profile_id: str | None = None,
) -> dict[str, Any]:
    return estimate_writer_profile_from_points(
        load_handwriting_points_jsonl(path),
        base_profile_id=base_profile_id,
        profile_id=profile_id,
    )


def _pen_down_segments(points: tuple[HandwritingPointRecord, ...]) -> list[list[HandwritingPointRecord]]:
    segments: list[list[HandwritingPointRecord]] = []
    current: list[HandwritingPointRecord] = []
    for point in sorted(points, key=lambda item: (item.t_ms, item.pen_state, item.x_mm, item.y_mm)):
        if point.pen_state == 1:
            current.append(point)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return segments


def _sample_mean_speed(
    points: tuple[HandwritingPointRecord, ...],
    segments: list[list[HandwritingPointRecord]],
) -> float | None:
    values: list[float] = []
    for segment in segments:
        if len(segment) < 2:
            continue
        duration_s = max((segment[-1].t_ms - segment[0].t_ms) / 1000.0, 1e-6)
        distance = sum(
            _distance(a, b)
            for a, b in zip(segment, segment[1:], strict=False)
        )
        if distance > 0:
            values.append(distance / duration_s)
    return _safe_mean(values)


def _sample_mean_spacing(segments: list[list[HandwritingPointRecord]]) -> float | None:
    values: list[float] = []
    for prev, curr in zip(segments, segments[1:], strict=False):
        values.append(
            _distance(
                prev[-1],
                curr[0],
            )
        )
    return _safe_mean(values)


def _sample_slant_deg(points: tuple[HandwritingPointRecord, ...]) -> float | None:
    vectors: list[float] = []
    pen_down_points = [point for point in points if point.pen_state == 1]
    for a, b in zip(pen_down_points, pen_down_points[1:], strict=False):
        dx = b.x_mm - a.x_mm
        dy = b.y_mm - a.y_mm
        if dx == 0.0 and dy == 0.0:
            continue
        vectors.append(math.degrees(math.atan2(dx, max(abs(dy), 1e-6))))
    return _safe_mean(vectors)


def _sample_baseline_drift_mm(segments: list[list[HandwritingPointRecord]]) -> float | None:
    if len(segments) < 2:
        return None
    centroids = [mean(point.y_mm for point in segment) for segment in segments if segment]
    if len(centroids) < 2:
        return None
    return abs(centroids[-1] - centroids[0])


def _sample_tremor_mm(
    points: tuple[HandwritingPointRecord, ...],
    segments: list[list[HandwritingPointRecord]],
) -> float | None:
    residuals: list[float] = []
    for segment in segments:
        if len(segment) < 3:
            continue
        start = segment[0]
        end = segment[-1]
        duration = max(end.t_ms - start.t_ms, 1)
        for point in segment[1:-1]:
            ratio = (point.t_ms - start.t_ms) / duration
            interp_x = start.x_mm + (end.x_mm - start.x_mm) * ratio
            interp_y = start.y_mm + (end.y_mm - start.y_mm) * ratio
            residuals.append(_distance((point.x_mm, point.y_mm), (interp_x, interp_y)))
    return _safe_mean(residuals)


def _profile_params_from_summary(
    summary: dict[str, Any],
    base_params: WriterProfileParameters,
) -> WriterProfileParameters:
    mean_speed = _prefer_balanced(summary, "mean_speed_mm_s", base_params.speed_mean_mm_s)
    spacing_mean = _prefer_balanced(summary, "spacing_mean_mm", base_params.spacing_mean_mm)
    slant = _prefer_balanced(summary, "slant_deg", base_params.slant_deg)
    drift = _prefer_balanced(summary, "baseline_drift_mm", base_params.baseline_drift_mm)
    tremor = _prefer_balanced(summary, "tremor_mm", base_params.tremor_mm)
    speed_cv = _prefer_balanced(summary, "speed_cv", base_params.timing_jitter_cv)
    pressure_mean = _prefer_balanced(summary, "terminal_pressure_mean", 1.0)
    pressure_cv = _prefer_balanced(summary, "terminal_pressure_cv", 0.0)

    return WriterProfileParameters(
        slant_deg=_clamp(slant, -15.0, 15.0),
        spacing_mean_mm=_clamp(spacing_mean, 0.5, 4.0),
        speed_mean_mm_s=_clamp(mean_speed, 8.0, 120.0),
        harai_gain=_clamp(base_params.harai_gain * (1.0 + max(0.0, 1.0 - pressure_mean) * 0.15), 0.5, 1.5),
        hane_gain=_clamp(base_params.hane_gain * (1.0 + pressure_cv * 0.5), 0.5, 1.5),
        tome_gain=_clamp(base_params.tome_gain * (1.0 + max(0.0, pressure_mean - 1.0) * 0.15), 0.5, 1.5),
        timing_jitter_cv=_clamp(max(speed_cv * 0.8, 0.03), 0.03, 0.4),
        tremor_mm=_clamp(max(tremor or base_params.tremor_mm, base_params.tremor_mm), 0.005, 0.15),
        baseline_drift_mm=_clamp(max(abs(drift), base_params.baseline_drift_mm), 0.0, 2.0),
        shape_variation=_clamp(max(tremor or base_params.shape_variation, 0.0) * 1.2, 0.0, 0.15),
        layout_variation=_clamp(
            max(
                abs(drift) * 0.25 + _prefer_balanced(summary, "spacing_cv", 0.0) * 0.15,
                base_params.layout_variation,
            ),
            0.0,
            0.2,
        ),
    )


def _derived_profile_id(base_profile_id: str, summary: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "base_profile_id": base_profile_id,
            "sample_count": summary["sample_count"],
            "writer_count": summary["writer_count"],
            "text_count": summary["text_count"],
            "mean_speed_mm_s": summary["mean_speed_mm_s"],
            "spacing_mean_mm": summary["spacing_mean_mm"],
            "slant_deg": summary["slant_deg"],
            "baseline_drift_mm": summary["baseline_drift_mm"],
            "tremor_mm": summary["tremor_mm"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return f"{base_profile_id}-data-prior-{hashlib.sha256(payload).hexdigest()[:8]}"


def _prior_notes(base_notes: str, summary: dict[str, Any]) -> str:
    note_parts = [base_notes.strip()] if base_notes.strip() else []
    note_parts.append(
        "data-driven prior from "
        f"{summary['sample_count']} samples / {summary['writer_count']} writers"
    )
    if summary.get("balanced_writer_count", 0) > 1:
        note_parts.append("writer-balanced aggregation")
    return "; ".join(note_parts)


def _distance(a: Any, b: Any) -> float:
    ax, ay = _coords(a)
    bx, by = _coords(b)
    return math.hypot(bx - ax, by - ay)


def _coords(point: Any) -> tuple[float, float]:
    if isinstance(point, tuple) and len(point) == 2:
        return float(point[0]), float(point[1])
    return float(point.x_mm), float(point.y_mm)


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(mean(values)), 4)


def _safe_cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = float(mean(values))
    if avg == 0.0:
        return 0.0
    return round(float(pstdev(values)) / abs(avg), 4)


def _clamp(value: float, lower: float, upper: float) -> float:
    return round(max(lower, min(upper, float(value))), 4)


def _prefer_balanced(summary: dict[str, Any], key: str, fallback: float) -> float:
    balanced_key = f"balanced_{key}"
    balanced_value = summary.get(balanced_key)
    if summary.get("balanced_writer_count", 0) > 0 and balanced_value is not None:
        return float(balanced_value)
    value = summary.get(key)
    if value is not None:
        return float(value)
    return float(fallback)

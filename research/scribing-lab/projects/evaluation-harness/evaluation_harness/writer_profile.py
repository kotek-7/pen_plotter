from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


def _ensure_paths() -> None:
    current = Path(__file__).resolve()
    repo_root: Path | None = None
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "research").is_dir():
            repo_root = parent
            break
    if repo_root is None:
        raise RuntimeError("Cannot locate pen_plotter repository root")

    paths = [
        repo_root,
        repo_root / "research" / "scribing-lab" / "projects" / "writer-profile",
    ]
    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


_ensure_paths()

from writer_profile import WriterProfile, WriterProfileParameters, get_profile  # noqa: E402

BASELINE_PROFILE_ID = "baseline-neat"
BASELINE_PROFILE = get_profile(BASELINE_PROFILE_ID)


def resolve_writer_profile(profile_id: str) -> WriterProfile:
    try:
        return get_profile(profile_id)
    except Exception as exc:
        alias = _canonical_profile_id(profile_id)
        if alias != profile_id:
            try:
                return get_profile(alias)
            except Exception:
                pass
        raise


def _canonical_profile_id(profile_id: str) -> str:
    match = re.match(r"^(?P<base>.+?)-abx-\d{3}(?:-r\d{3})?$", profile_id)
    if match:
        return match.group("base")
    return profile_id


def writer_profile_metrics(profile: WriterProfile) -> dict[str, float | int | str]:
    params = profile.params
    return {
        "writer_profile_version": profile.version,
        "writer_profile_slant_deg": params.slant_deg,
        "writer_profile_spacing_mean_mm": params.spacing_mean_mm,
        "writer_profile_speed_mean_mm_s": params.speed_mean_mm_s,
        "writer_profile_harai_gain": params.harai_gain,
        "writer_profile_hane_gain": params.hane_gain,
        "writer_profile_tome_gain": params.tome_gain,
        "writer_profile_timing_jitter_cv": params.timing_jitter_cv,
        "writer_profile_tremor_mm": params.tremor_mm,
        "writer_profile_baseline_drift_mm": params.baseline_drift_mm,
        "writer_profile_shape_variation": params.shape_variation,
        "writer_profile_layout_variation": params.layout_variation,
    }


def writer_profile_artifact(profile: WriterProfile) -> dict[str, Any]:
    return profile.to_dict()


def apply_writer_profile_to_layout_config(config: Any, profile: WriterProfile) -> Any:
    return replace(
        config,
        slant_deg=profile.params.slant_deg,
        baseline_drift_mm=profile.params.baseline_drift_mm,
    )


def apply_writer_profile_to_structure_uniform_config(config: Any, profile: WriterProfile) -> Any:
    params = profile.params
    return replace(
        config,
        char_spacing=max(
            0.0,
            config.char_spacing + (params.spacing_mean_mm - BASELINE_PROFILE.params.spacing_mean_mm),
        ),
        draw_speed_mm_s=max(
            1.0,
            config.draw_speed_mm_s + (params.speed_mean_mm_s - BASELINE_PROFILE.params.speed_mean_mm_s),
        ),
    )


def apply_writer_profile_to_structure_motion_config(config: Any, profile: WriterProfile) -> Any:
    params = profile.params
    return replace(
        config,
        char_spacing=max(
            0.0,
            config.char_spacing
            + _blend_delta(
                params.spacing_mean_mm - BASELINE_PROFILE.params.spacing_mean_mm,
                strength=0.85,
            ),
        ),
        timing_jitter_cv=max(
            0.0,
            config.timing_jitter_cv
            + _blend_delta(
                params.timing_jitter_cv - BASELINE_PROFILE.params.timing_jitter_cv,
                strength=0.55,
            ),
        ),
        tremor_mm=max(
            0.0,
            config.tremor_mm
            + _blend_delta(
                params.tremor_mm - BASELINE_PROFILE.params.tremor_mm,
                strength=0.55,
            ),
        ),
        shape_variation=max(
            0.0,
            config.shape_variation + _blend_delta(params.shape_variation, strength=0.85),
        ),
        layout_variation=max(
            0.0,
            config.layout_variation + _blend_delta(params.layout_variation, strength=0.75),
        ),
    )


def apply_writer_profile_to_motion_config(config: Any, profile: WriterProfile) -> Any:
    params = profile.params
    return replace(
        config,
        draw_speed_mm_s=max(
            1.0,
            config.draw_speed_mm_s + (params.speed_mean_mm_s - BASELINE_PROFILE.params.speed_mean_mm_s),
        ),
        timing_jitter_cv=max(
            0.0,
            config.timing_jitter_cv
            + _blend_delta(
                params.timing_jitter_cv - BASELINE_PROFILE.params.timing_jitter_cv,
                strength=0.55,
            ),
        ),
        tremor_mm=max(
            0.0,
            config.tremor_mm
            + _blend_delta(
                params.tremor_mm - BASELINE_PROFILE.params.tremor_mm,
                strength=0.55,
            ),
        ),
        harai_min_pressure=_scaled_pressure(
            config.harai_min_pressure,
            params.harai_gain,
            BASELINE_PROFILE.params.harai_gain,
        ),
        hane_min_pressure=_scaled_pressure(
            config.hane_min_pressure,
            params.hane_gain,
            BASELINE_PROFILE.params.hane_gain,
        ),
        tome_terminal_pressure=_scaled_pressure(
            config.tome_terminal_pressure,
            params.tome_gain,
            BASELINE_PROFILE.params.tome_gain,
        ),
    )


def build_revision_profile(
    profile: WriterProfile,
    proposed_changes: list[dict[str, Any]],
    *,
    revision_profile_id: str | None = None,
    created_from_experiment: str | None = None,
) -> dict[str, Any]:
    params = profile.params
    applied_changes: list[dict[str, Any]] = []
    unapplied_changes: list[dict[str, Any]] = []

    for change in proposed_changes:
        updated_params, applied = _apply_revision_change(params, change)
        if applied:
            params = updated_params
            applied_changes.append(change)
        else:
            unapplied_changes.append(change)

    revision_profile = replace(
        profile,
        profile_id=revision_profile_id or f"{profile.profile_id}-revision",
        version=profile.version + 1,
        source="derived",
        parent_profile=profile.profile_id,
        created_from_experiment=created_from_experiment,
        params=params,
        notes=_revision_notes(profile.notes, applied_changes, unapplied_changes),
    )
    return {
        "profile": revision_profile,
        "applied_changes": applied_changes,
        "unapplied_changes": unapplied_changes,
    }


def _apply_revision_change(
    params: WriterProfileParameters,
    change: dict[str, Any],
) -> tuple[WriterProfileParameters, bool]:
    parameter = str(change.get("parameter", ""))
    direction = str(change.get("direction", ""))
    amount_hint = change.get("amount_hint")

    if parameter == "terminal_gains" and direction == "increase-contrast":
        spread = float(amount_hint or 0.1)
        return (
            replace(
                params,
                harai_gain=max(0.0, params.harai_gain - spread),
                hane_gain=max(0.0, params.hane_gain),
                tome_gain=max(0.0, params.tome_gain + spread),
            ),
            True,
        )

    if amount_hint is None:
        return params, False

    delta = float(amount_hint)
    if direction == "decrease":
        delta = -delta
    elif direction not in {"increase", "adjust"}:
        return params, False

    mapping = {
        "slant_deg": "slant_deg",
        "spacing_mean_mm": "spacing_mean_mm",
        "speed_mean_mm_s": "speed_mean_mm_s",
        "harai_gain": "harai_gain",
        "hane_gain": "hane_gain",
        "tome_gain": "tome_gain",
        "timing_jitter_cv": "timing_jitter_cv",
        "tremor_mm": "tremor_mm",
        "baseline_drift_mm": "baseline_drift_mm",
        "shape_variation": "shape_variation",
        "layout_variation": "layout_variation",
    }
    attr = mapping.get(parameter)
    if attr is None:
        return params, False

    current_value = float(getattr(params, attr))
    updated_value = max(0.0, current_value + delta)
    return replace(params, **{attr: updated_value}), True


def _revision_notes(
    base_notes: str,
    applied_changes: list[dict[str, Any]],
    unapplied_changes: list[dict[str, Any]],
) -> str:
    note_parts = [base_notes.strip()] if base_notes.strip() else []
    if applied_changes:
        note_parts.append(f"applied={len(applied_changes)}")
    if unapplied_changes:
        note_parts.append(f"unapplied={len(unapplied_changes)}")
    return "; ".join(note_parts)


def _scaled_pressure(base_pressure: float, profile_gain: float, baseline_gain: float) -> float:
    if baseline_gain <= 0:
        return base_pressure
    return max(0.0, base_pressure * (profile_gain / baseline_gain))


def _blend_delta(delta: float, *, strength: float) -> float:
    return delta * max(0.0, min(strength, 1.0))

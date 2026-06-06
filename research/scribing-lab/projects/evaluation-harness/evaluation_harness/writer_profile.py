from __future__ import annotations

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

from writer_profile import WriterProfile, get_profile  # noqa: E402

BASELINE_PROFILE_ID = "baseline-neat"
BASELINE_PROFILE = get_profile(BASELINE_PROFILE_ID)


def resolve_writer_profile(profile_id: str) -> WriterProfile:
    return get_profile(profile_id)


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
            config.char_spacing + (params.spacing_mean_mm - BASELINE_PROFILE.params.spacing_mean_mm),
        ),
        timing_jitter_cv=max(
            0.0,
            config.timing_jitter_cv + (params.timing_jitter_cv - BASELINE_PROFILE.params.timing_jitter_cv),
        ),
        tremor_mm=max(
            0.0,
            config.tremor_mm + (params.tremor_mm - BASELINE_PROFILE.params.tremor_mm),
        ),
        shape_variation=max(0.0, config.shape_variation + params.shape_variation),
        layout_variation=max(0.0, config.layout_variation + params.layout_variation),
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
            config.timing_jitter_cv + (params.timing_jitter_cv - BASELINE_PROFILE.params.timing_jitter_cv),
        ),
        tremor_mm=max(
            0.0,
            config.tremor_mm + (params.tremor_mm - BASELINE_PROFILE.params.tremor_mm),
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


def _scaled_pressure(base_pressure: float, profile_gain: float, baseline_gain: float) -> float:
    if baseline_gain <= 0:
        return base_pressure
    return max(0.0, base_pressure * (profile_gain / baseline_gain))

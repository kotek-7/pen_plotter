from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from writer_profile.models import WriterProfile, WriterProfileParameters


SCHEMA_VERSION = 1
PROFILE_REGISTRY_ID = "writer-profile-manual-mvp"
BUILTIN_PROFILE_ORDER = ("baseline-neat", "fast-casual", "shaky-slow")
BUILTIN_PROFILE_IDS = frozenset(BUILTIN_PROFILE_ORDER)

_PROFILES = OrderedDict(
    (
        (
            "baseline-neat",
            WriterProfile(
                profile_id="baseline-neat",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=2.0,
                    spacing_mean_mm=1.2,
                    speed_mean_mm_s=40.0,
                    harai_gain=1.0,
                    hane_gain=1.0,
                    tome_gain=1.0,
                    timing_jitter_cv=0.08,
                    tremor_mm=0.015,
                    baseline_drift_mm=0.0,
                    shape_variation=0.0,
                    layout_variation=0.0,
                ),
                notes="Balanced baseline profile for comparison runs.",
            ),
        ),
        (
            "fast-casual",
            WriterProfile(
                profile_id="fast-casual",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=6.5,
                    spacing_mean_mm=1.08,
                    speed_mean_mm_s=50.0,
                    harai_gain=1.12,
                    hane_gain=1.08,
                    tome_gain=0.92,
                    timing_jitter_cv=0.18,
                    tremor_mm=0.024,
                    baseline_drift_mm=0.5,
                    shape_variation=0.06,
                    layout_variation=0.03,
                ),
                parent_profile="baseline-neat",
                notes="Faster, looser profile for casual handwriting comparison.",
            ),
        ),
        (
            "shaky-slow",
            WriterProfile(
                profile_id="shaky-slow",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=-1.5,
                    spacing_mean_mm=1.35,
                    speed_mean_mm_s=28.0,
                    harai_gain=0.9,
                    hane_gain=1.05,
                    tome_gain=1.1,
                    timing_jitter_cv=0.22,
                    tremor_mm=0.06,
                    baseline_drift_mm=0.8,
                    shape_variation=0.06,
                    layout_variation=0.05,
                ),
                parent_profile="baseline-neat",
                notes="Slow and unstable profile for variation-heavy comparisons.",
            ),
        ),
    )
)


class WriterProfileLookupError(KeyError):
    pass


def get_profile(profile_id: str) -> WriterProfile:
    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise WriterProfileLookupError(profile_id) from exc


def iter_builtin_profiles() -> tuple[WriterProfile, ...]:
    return tuple(_PROFILES.values())


def export_registry() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": PROFILE_REGISTRY_ID,
        "profile_count": len(_PROFILES),
        "profiles": [profile.to_dict() for profile in _PROFILES.values()],
    }


def export_registry_json(indent: int = 2) -> str:
    return json.dumps(export_registry(), ensure_ascii=False, indent=indent, sort_keys=True) + "\n"

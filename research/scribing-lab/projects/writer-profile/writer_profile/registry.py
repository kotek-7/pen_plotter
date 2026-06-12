from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from writer_profile.models import WriterProfile, WriterProfileParameters


SCHEMA_VERSION = 1
PROFILE_REGISTRY_ID = "writer-profile-manual-mvp"
BUILTIN_PROFILE_ORDER = (
    "baseline-neat",
    "glyph-neat",
    "steady-neat",
    "fast-casual",
    "compact-casual",
    "micro-casual",
    "flow-casual",
    "textured-casual",
    "textured-steady",
    "textured-tight",
    "shaky-slow",
)
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
            "glyph-neat",
            WriterProfile(
                profile_id="glyph-neat",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=2.2,
                    spacing_mean_mm=1.17,
                    speed_mean_mm_s=41.0,
                    harai_gain=1.03,
                    hane_gain=1.01,
                    tome_gain=0.99,
                    timing_jitter_cv=0.12,
                    tremor_mm=0.018,
                    baseline_drift_mm=0.08,
                    shape_variation=0.010,
                    layout_variation=0.006,
                ),
                parent_profile="baseline-neat",
                notes="Glyph-oriented neat profile for short kana, punctuation, and Latin comparisons.",
            ),
        ),
        (
            "steady-neat",
            WriterProfile(
                profile_id="steady-neat",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=2.4,
                    spacing_mean_mm=1.18,
                    speed_mean_mm_s=40.5,
                    harai_gain=1.02,
                    hane_gain=1.01,
                    tome_gain=0.99,
                    timing_jitter_cv=0.09,
                    tremor_mm=0.016,
                    baseline_drift_mm=0.05,
                    shape_variation=0.008,
                    layout_variation=0.004,
                ),
                parent_profile="glyph-neat",
                notes="Subtle neat profile for punctuation-heavy and short-kanji comparisons.",
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
            "compact-casual",
            WriterProfile(
                profile_id="compact-casual",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=3.0,
                    spacing_mean_mm=1.03,
                    speed_mean_mm_s=44.0,
                    harai_gain=1.06,
                    hane_gain=1.03,
                    tome_gain=0.98,
                    timing_jitter_cv=0.10,
                    tremor_mm=0.017,
                    baseline_drift_mm=0.1,
                    shape_variation=0.02,
                    layout_variation=0.01,
                ),
                parent_profile="fast-casual",
                notes="Compact casual profile for single-character and symbol-heavy comparisons.",
            ),
        ),
        (
            "micro-casual",
            WriterProfile(
                profile_id="micro-casual",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=4.2,
                    spacing_mean_mm=0.98,
                    speed_mean_mm_s=43.0,
                    harai_gain=1.07,
                    hane_gain=1.05,
                    tome_gain=0.97,
                    timing_jitter_cv=0.11,
                    tremor_mm=0.018,
                    baseline_drift_mm=0.18,
                    shape_variation=0.028,
                    layout_variation=0.012,
                ),
                parent_profile="compact-casual",
                notes="Micro casual profile for single-character, digits, and punctuation-heavy comparisons.",
            ),
        ),
        (
            "flow-casual",
            WriterProfile(
                profile_id="flow-casual",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=4.8,
                    spacing_mean_mm=1.06,
                    speed_mean_mm_s=41.5,
                    harai_gain=1.09,
                    hane_gain=1.05,
                    tome_gain=0.96,
                    timing_jitter_cv=0.13,
                    tremor_mm=0.021,
                    baseline_drift_mm=0.55,
                    shape_variation=0.024,
                    layout_variation=0.014,
                ),
                parent_profile="textured-casual",
                notes="Flow casual profile for longer kana and symbol-heavy comparisons.",
            ),
        ),
        (
            "textured-casual",
            WriterProfile(
                profile_id="textured-casual",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=4.0,
                    spacing_mean_mm=1.06,
                    speed_mean_mm_s=42.5,
                    harai_gain=1.1,
                    hane_gain=1.06,
                    tome_gain=0.95,
                    timing_jitter_cv=0.15,
                    tremor_mm=0.022,
                    baseline_drift_mm=0.9,
                    shape_variation=0.035,
                    layout_variation=0.02,
                ),
                parent_profile="compact-casual",
                notes="Textured casual profile for longer text and symbol-heavy comparison runs.",
            ),
        ),
        (
            "textured-steady",
            WriterProfile(
                profile_id="textured-steady",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=4.1,
                    spacing_mean_mm=1.01,
                    speed_mean_mm_s=41.5,
                    harai_gain=1.08,
                    hane_gain=1.04,
                    tome_gain=0.96,
                    timing_jitter_cv=0.11,
                    tremor_mm=0.017,
                    baseline_drift_mm=0.48,
                    shape_variation=0.024,
                    layout_variation=0.014,
                ),
                parent_profile="textured-casual",
                notes="Stable textured profile for longer text and symbol-heavy comparison runs.",
            ),
        ),
        (
            "textured-tight",
            WriterProfile(
                profile_id="textured-tight",
                version=1,
                source="manual",
                allowed_use="research-baseline",
                params=WriterProfileParameters(
                    slant_deg=4.0,
                    spacing_mean_mm=0.92,
                    speed_mean_mm_s=41.0,
                    harai_gain=1.07,
                    hane_gain=1.03,
                    tome_gain=0.96,
                    timing_jitter_cv=0.09,
                    tremor_mm=0.014,
                    baseline_drift_mm=0.34,
                    shape_variation=0.020,
                    layout_variation=0.011,
                ),
                parent_profile="textured-steady",
                notes="Tighter textured profile for longer text and spacing-sensitive comparisons.",
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

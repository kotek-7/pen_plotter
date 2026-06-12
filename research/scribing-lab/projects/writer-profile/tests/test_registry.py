import pytest

from writer_profile import (
    BUILTIN_PROFILE_IDS,
    BUILTIN_PROFILE_ORDER,
    PROFILE_REGISTRY_ID,
    SCHEMA_VERSION,
    export_registry,
    export_registry_json,
    get_profile,
    iter_builtin_profiles,
)
from writer_profile.registry import WriterProfileLookupError


def test_builtin_profile_order_is_stable() -> None:
    assert BUILTIN_PROFILE_ORDER == (
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
    assert BUILTIN_PROFILE_IDS == set(BUILTIN_PROFILE_ORDER)
    assert [profile.profile_id for profile in iter_builtin_profiles()] == list(
        BUILTIN_PROFILE_ORDER
    )


def test_export_registry_is_deterministic() -> None:
    first = export_registry()
    second = export_registry()

    assert first == second
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["registry_id"] == PROFILE_REGISTRY_ID
    assert first["profile_count"] == len(BUILTIN_PROFILE_ORDER)
    assert [item["profile_id"] for item in first["profiles"]] == list(BUILTIN_PROFILE_ORDER)


def test_export_registry_json_is_stable() -> None:
    json_text = export_registry_json()

    assert '"schema_version": 1' in json_text
    assert '"registry_id": "writer-profile-manual-mvp"' in json_text
    assert json_text.endswith("\n")


def test_get_profile_returns_known_profile() -> None:
    profile = get_profile("baseline-neat")

    assert profile.profile_id == "baseline-neat"
    assert profile.params.speed_mean_mm_s == 40.0
    assert profile.params.slant_deg == 2.0


def test_fast_casual_profile_is_distinct_from_baseline() -> None:
    profile = get_profile("fast-casual")

    assert profile.profile_id == "fast-casual"
    assert profile.parent_profile == "baseline-neat"
    assert profile.params.speed_mean_mm_s > 40.0
    assert profile.params.timing_jitter_cv > get_profile("baseline-neat").params.timing_jitter_cv
    assert profile.params.tremor_mm > get_profile("baseline-neat").params.tremor_mm
    assert profile.params.baseline_drift_mm > get_profile("baseline-neat").params.baseline_drift_mm


def test_steady_neat_profile_targets_subtle_variation() -> None:
    profile = get_profile("steady-neat")

    assert profile.profile_id == "steady-neat"
    assert profile.parent_profile == "glyph-neat"
    assert profile.params.spacing_mean_mm > get_profile("glyph-neat").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s <= get_profile("glyph-neat").params.speed_mean_mm_s
    assert profile.params.timing_jitter_cv < get_profile("glyph-neat").params.timing_jitter_cv
    assert profile.params.tremor_mm < get_profile("glyph-neat").params.tremor_mm
    assert profile.params.shape_variation < get_profile("glyph-neat").params.shape_variation


def test_glyph_neat_profile_targets_single_glyph_variation() -> None:
    profile = get_profile("glyph-neat")

    assert profile.profile_id == "glyph-neat"
    assert profile.parent_profile == "baseline-neat"
    assert profile.params.spacing_mean_mm < get_profile("baseline-neat").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s > get_profile("baseline-neat").params.speed_mean_mm_s
    assert profile.params.timing_jitter_cv > get_profile("baseline-neat").params.timing_jitter_cv
    assert profile.params.tremor_mm > get_profile("baseline-neat").params.tremor_mm
    assert profile.params.shape_variation > get_profile("baseline-neat").params.shape_variation


def test_compact_casual_profile_targets_tighter_layout() -> None:
    profile = get_profile("compact-casual")

    assert profile.profile_id == "compact-casual"
    assert profile.parent_profile == "fast-casual"
    assert profile.params.spacing_mean_mm < get_profile("fast-casual").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s < get_profile("fast-casual").params.speed_mean_mm_s
    assert profile.params.baseline_drift_mm < get_profile("fast-casual").params.baseline_drift_mm
    assert profile.params.tremor_mm < get_profile("fast-casual").params.tremor_mm


def test_micro_casual_profile_targets_symbols_and_digits() -> None:
    profile = get_profile("micro-casual")

    assert profile.profile_id == "micro-casual"
    assert profile.parent_profile == "compact-casual"
    assert profile.params.spacing_mean_mm < get_profile("compact-casual").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s <= get_profile("compact-casual").params.speed_mean_mm_s
    assert profile.params.baseline_drift_mm > get_profile("compact-casual").params.baseline_drift_mm
    assert profile.params.tremor_mm > get_profile("compact-casual").params.tremor_mm


def test_flow_casual_profile_targets_longer_text_flow() -> None:
    profile = get_profile("flow-casual")

    assert profile.profile_id == "flow-casual"
    assert profile.parent_profile == "textured-casual"
    assert profile.params.spacing_mean_mm >= get_profile("micro-casual").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s < get_profile("fast-casual").params.speed_mean_mm_s
    assert profile.params.baseline_drift_mm > get_profile("compact-casual").params.baseline_drift_mm
    assert profile.params.tremor_mm > get_profile("compact-casual").params.tremor_mm


def test_textured_casual_profile_targets_more_motion_texture() -> None:
    profile = get_profile("textured-casual")

    assert profile.profile_id == "textured-casual"
    assert profile.parent_profile == "compact-casual"
    assert profile.params.spacing_mean_mm > get_profile("compact-casual").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s < get_profile("fast-casual").params.speed_mean_mm_s
    assert profile.params.baseline_drift_mm > get_profile("compact-casual").params.baseline_drift_mm
    assert profile.params.tremor_mm > get_profile("compact-casual").params.tremor_mm


def test_textured_steady_profile_targets_stable_texture() -> None:
    profile = get_profile("textured-steady")

    assert profile.profile_id == "textured-steady"
    assert profile.parent_profile == "textured-casual"
    assert profile.params.spacing_mean_mm < get_profile("textured-casual").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s <= get_profile("textured-casual").params.speed_mean_mm_s
    assert profile.params.timing_jitter_cv < get_profile("textured-casual").params.timing_jitter_cv
    assert profile.params.tremor_mm < get_profile("textured-casual").params.tremor_mm
    assert profile.params.baseline_drift_mm < get_profile("textured-casual").params.baseline_drift_mm


def test_textured_tight_profile_targets_spacing_sensitive_text() -> None:
    profile = get_profile("textured-tight")

    assert profile.profile_id == "textured-tight"
    assert profile.parent_profile == "textured-steady"
    assert profile.params.spacing_mean_mm < get_profile("textured-steady").params.spacing_mean_mm
    assert profile.params.speed_mean_mm_s <= get_profile("textured-steady").params.speed_mean_mm_s
    assert profile.params.timing_jitter_cv < get_profile("textured-steady").params.timing_jitter_cv
    assert profile.params.tremor_mm < get_profile("textured-steady").params.tremor_mm
    assert profile.params.baseline_drift_mm < get_profile("textured-steady").params.baseline_drift_mm


def test_get_profile_rejects_unknown_profile() -> None:
    with pytest.raises(WriterProfileLookupError):
        get_profile("unknown-profile")

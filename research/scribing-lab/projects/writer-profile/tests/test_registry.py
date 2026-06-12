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
    assert BUILTIN_PROFILE_ORDER == ("baseline-neat", "fast-casual", "shaky-slow")
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


def test_get_profile_rejects_unknown_profile() -> None:
    with pytest.raises(WriterProfileLookupError):
        get_profile("unknown-profile")

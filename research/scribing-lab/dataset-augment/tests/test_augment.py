from __future__ import annotations

import random

from scribing_dataset_augment.augment import AugmentParams, _augment_once, augment_dataset


def _sample(char: str = "あ") -> dict:
    return {
        "sampleId": "s_000001",
        "char": char,
        "canvas": {"width": 100, "height": 100},
        "guide": {"cell": {"x": 18, "y": 18, "width": 64, "height": 64}},
        "strokes": [
            {"strokeIndex": 0, "points": [{"x": 30, "y": 30, "t": 0, "pressure": 0.5},
                                          {"x": 70, "y": 70, "t": 10, "pressure": 0.6}]},
            {"strokeIndex": 1, "points": [{"x": 40, "y": 60, "t": 30, "pressure": 0.4}]},
        ],
    }


def test_count_and_originals():
    samples = [_sample("あ"), _sample("い")]
    params = AugmentParams()
    only = augment_dataset(samples, copies=3, params=params, seed=1, include_originals=False)
    assert len(only) == 6
    withorig = augment_dataset(samples, copies=3, params=params, seed=1, include_originals=True)
    assert len(withorig) == 8


def test_structure_and_metadata_preserved():
    s = _sample("あ")
    rng = random.Random(1)
    aug = _augment_once(s, rng, AugmentParams(), 0)
    assert aug["char"] == "あ"
    assert aug["guide"] == s["guide"]
    assert aug["augmentedFrom"] == "s_000001"
    assert aug["sampleId"] == "s_000001_aug00"
    # stroke 数・点数・t/pressure は保持
    assert [len(st["points"]) for st in aug["strokes"]] == [2, 1]
    assert aug["strokes"][0]["points"][0]["t"] == 0
    assert aug["strokes"][0]["points"][0]["pressure"] == 0.5


def test_identity_when_zero_params():
    s = _sample("う")
    rng = random.Random(0)
    aug = _augment_once(s, rng, AugmentParams(rotate_deg=0, scale=0, shear=0, jitter=0), 0)
    for so, sa in zip(s["strokes"], aug["strokes"], strict=True):
        for po, pa in zip(so["points"], sa["points"], strict=True):
            assert abs(po["x"] - pa["x"]) < 1e-6
            assert abs(po["y"] - pa["y"]) < 1e-6


def test_deterministic_for_seed():
    s = [_sample("あ")]
    a = augment_dataset(s, copies=2, params=AugmentParams(), seed=7, include_originals=False)
    b = augment_dataset(s, copies=2, params=AugmentParams(), seed=7, include_originals=False)
    assert a == b

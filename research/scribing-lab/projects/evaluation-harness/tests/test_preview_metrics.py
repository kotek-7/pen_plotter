from __future__ import annotations

import numpy as np
from matplotlib import image as mpl_image

from evaluation_harness.preview_metrics import (
    compare_preview_artifacts,
    summarize_preview_artifact,
)


def test_summarize_preview_artifact_reports_image_statistics(tmp_path) -> None:
    path = tmp_path / "preview.png"
    image = np.zeros((8, 8, 4), dtype=float)
    image[..., :3] = 1.0
    image[2:6, 2:6, :3] = 0.0
    image[..., 3] = 1.0
    mpl_image.imsave(path, image)

    summary = summarize_preview_artifact(str(path))

    assert summary is not None
    assert summary["width_px"] == 8
    assert summary["height_px"] == 8
    assert summary["foreground_ratio"] > 0.0
    assert summary["ink_density"] > 0.0
    assert "center_of_mass_x" in summary
    assert "center_of_mass_y" in summary


def test_compare_preview_artifacts_reports_similarity(tmp_path) -> None:
    baseline_path = tmp_path / "baseline.png"
    candidate_path = tmp_path / "candidate.png"
    baseline = np.ones((8, 8, 4), dtype=float)
    baseline[2:6, 2:6, :3] = 0.0
    baseline[..., 3] = 1.0
    candidate = np.ones((8, 8, 4), dtype=float)
    candidate[1:5, 1:5, :3] = 0.0
    candidate[..., 3] = 1.0
    mpl_image.imsave(baseline_path, baseline)
    mpl_image.imsave(candidate_path, candidate)

    baseline_summary = summarize_preview_artifact(str(baseline_path))
    candidate_summary = summarize_preview_artifact(str(candidate_path))
    comparison = compare_preview_artifacts(baseline_summary, candidate_summary)

    assert comparison is not None
    assert comparison["ssim_proxy"] <= 1.0
    assert comparison["mean_abs_difference"] >= 0.0
    assert comparison["center_of_mass_distance"] >= 0.0

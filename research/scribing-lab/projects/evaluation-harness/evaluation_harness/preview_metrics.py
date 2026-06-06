from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import image as mpl_image


def summarize_preview_artifact(path_text: str) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        return None

    data = path.read_bytes()
    summary: dict[str, Any] = {
        "path": str(path),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

    image = _load_preview_image(path)
    if image is None:
        return summary

    gray = _to_grayscale(image)
    if gray.size == 0:
        return summary

    summary.update(
        {
            "width_px": int(gray.shape[1]),
            "height_px": int(gray.shape[0]),
            "gray_mean": round(float(gray.mean()), 6),
            "gray_std": round(float(gray.std()), 6),
            "foreground_ratio": round(float(np.mean(gray < 0.92)), 6),
            "ink_density": round(float(np.mean(1.0 - gray)), 6),
        }
    )
    center_x, center_y = _center_of_mass(gray)
    if center_x is not None and center_y is not None:
        summary["center_of_mass_x"] = round(center_x, 6)
        summary["center_of_mass_y"] = round(center_y, 6)
    return summary


def compare_preview_artifacts(
    baseline: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if baseline is None or candidate is None:
        return None
    if "path" not in baseline or "path" not in candidate:
        return None

    baseline_image = _load_preview_image(Path(str(baseline["path"])))
    candidate_image = _load_preview_image(Path(str(candidate["path"])))
    if baseline_image is None or candidate_image is None:
        return None

    baseline_gray = _to_grayscale(baseline_image)
    candidate_gray = _to_grayscale(candidate_image)
    if baseline_gray.size == 0 or candidate_gray.size == 0:
        return None

    left, right = _resize_pair(baseline_gray, candidate_gray)
    diff = np.abs(left - right)
    ssim_proxy = _ssim_proxy(left, right)
    return {
        "ssim_proxy": round(ssim_proxy, 6),
        "mean_abs_difference": round(float(diff.mean()), 6),
        "max_abs_difference": round(float(diff.max()), 6),
        "foreground_ratio_delta": round(
            float(candidate.get("foreground_ratio", 0.0)) - float(baseline.get("foreground_ratio", 0.0)),
            6,
        ),
        "ink_density_delta": round(
            float(candidate.get("ink_density", 0.0)) - float(baseline.get("ink_density", 0.0)),
            6,
        ),
        "center_of_mass_distance": round(
            _center_distance(baseline, candidate),
            6,
        ),
    }


def _load_preview_image(path: Path) -> np.ndarray | None:
    try:
        image = np.asarray(mpl_image.imread(path), dtype=float)
    except (OSError, ValueError, SyntaxError):
        return None
    if image.size == 0:
        return None
    return image


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3:
        rgb = image[..., :3]
        if rgb.size and float(rgb.max()) > 1.5:
            rgb = rgb / 255.0
        gray = np.dot(rgb, np.array([0.299, 0.587, 0.114], dtype=float))
        if image.shape[-1] == 4:
            alpha = image[..., 3]
            if alpha.size and float(alpha.max()) > 1.5:
                alpha = alpha / 255.0
            gray = gray * alpha + (1.0 - alpha)
    else:
        return np.empty((0, 0), dtype=float)

    gray = np.asarray(gray, dtype=float)
    if gray.size and float(gray.max()) > 1.5:
        gray = gray / 255.0
    gray = np.clip(gray, 0.0, 1.0)
    return gray


def _resize_pair(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target_height = min(left.shape[0], right.shape[0], 256)
    target_width = min(left.shape[1], right.shape[1], 256)
    if target_height < 1 or target_width < 1:
        return left[:0, :0], right[:0, :0]
    return _resize_gray(left, target_height, target_width), _resize_gray(right, target_height, target_width)


def _resize_gray(image: np.ndarray, target_height: int, target_width: int) -> np.ndarray:
    if image.shape == (target_height, target_width):
        return image
    y_idx = np.linspace(0, image.shape[0] - 1, target_height).round().astype(int)
    x_idx = np.linspace(0, image.shape[1] - 1, target_width).round().astype(int)
    return image[np.ix_(y_idx, x_idx)]


def _ssim_proxy(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.size == 0 or right.size == 0:
        return 0.0

    mu_left = float(left.mean())
    mu_right = float(right.mean())
    var_left = float(left.var())
    var_right = float(right.var())
    cov = float(((left - mu_left) * (right - mu_right)).mean())
    c1 = 0.01**2
    c2 = 0.03**2
    numerator = (2 * mu_left * mu_right + c1) * (2 * cov + c2)
    denominator = (mu_left**2 + mu_right**2 + c1) * (var_left + var_right + c2)
    if denominator == 0.0:
        return 0.0
    return max(-1.0, min(1.0, numerator / denominator))


def _center_of_mass(gray: np.ndarray) -> tuple[float | None, float | None]:
    ink = 1.0 - gray
    total = float(ink.sum())
    if total <= 0.0:
        return None, None
    yy, xx = np.indices(gray.shape)
    return float((xx * ink).sum() / total), float((yy * ink).sum() / total)


def _center_distance(baseline: dict[str, Any], candidate: dict[str, Any]) -> float:
    keys = ("center_of_mass_x", "center_of_mass_y")
    if not all(key in baseline for key in keys) or not all(key in candidate for key in keys):
        return 0.0
    dx = float(candidate["center_of_mass_x"]) - float(baseline["center_of_mass_x"])
    dy = float(candidate["center_of_mass_y"]) - float(baseline["center_of_mass_y"])
    return float(np.hypot(dx, dy))

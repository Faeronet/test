"""Quality scoring used downstream by the page router (e.g. to flag a page
as `bad_scan`) and the QA service.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class QualityReport:
    contrast_score: float
    noise_score: float
    estimated_dpi: int
    skew_angle_deg: float
    fg_ratio: float
    text_density: float
    warnings: list[str]


def estimate_quality(gray: np.ndarray, binary: np.ndarray, skew_deg: float) -> QualityReport:
    h, w = gray.shape[:2]
    contrast = float(np.clip(gray.std() / 80.0, 0.0, 1.0))
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    noise = float(np.clip(lap_var / 1500.0, 0.0, 1.0))

    # Foreground ratio after binarisation.
    fg_ratio = float(np.count_nonzero(binary) / max(h * w, 1))

    # Cheap text-density proxy: ratio of small connected components in the
    # binarised image. Many small blobs == probably text-heavy.
    text_density = _text_density(binary)

    # Estimated DPI is a wild guess from page width: assume A4 portrait at
    # ≥1000 px ≈ 200 DPI. Used only as a hint downstream.
    estimated_dpi = int(round(max(72, min(600, w / 8.27))))

    warnings: list[str] = []
    if contrast < 0.25:
        warnings.append("low_contrast")
    if noise < 0.15:
        warnings.append("noisy_or_blurred")
    if fg_ratio < 0.005:
        warnings.append("almost_blank_page")
    if fg_ratio > 0.8:
        warnings.append("almost_solid_page")
    if abs(skew_deg) > 5:
        warnings.append("high_skew")

    return QualityReport(
        contrast_score=contrast,
        noise_score=noise,
        estimated_dpi=estimated_dpi,
        skew_angle_deg=skew_deg,
        fg_ratio=fg_ratio,
        text_density=text_density,
        warnings=warnings,
    )


def _text_density(binary: np.ndarray) -> float:
    h, w = binary.shape[:2]
    num, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return 0.0

    small_blobs = 0
    for i in range(1, num):
        a = int(stats[i, cv2.CC_STAT_AREA])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if a <= 0:
            continue
        if 10 <= a <= 600 and 4 <= bw <= 60 and 4 <= bh <= 60:
            small_blobs += 1
    return float(min(1.0, small_blobs / max(1.0, (h * w) / 50_000)))

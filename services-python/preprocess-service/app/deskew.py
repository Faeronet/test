"""Estimate and correct skew angle of a binarised drawing using the Radon-like
projection profile method (variance of horizontal pixel sums).

This is sensitive enough for most engineering drawings while remaining cheap
on CPU. Range is constrained to ±max_angle_deg to avoid catastrophic 90°
rotations for pages where the dominant axis is vertical.
"""
from __future__ import annotations

import cv2
import numpy as np


def estimate_skew_deg(binary: np.ndarray, max_angle: float = 10.0, step: float = 0.2) -> float:
    """Returns skew angle in degrees; positive = rotate clockwise to deskew."""
    h, w = binary.shape[:2]
    if h * w == 0:
        return 0.0
    if max(h, w) > 2000:
        scale = 2000.0 / max(h, w)
        binary = cv2.resize(binary, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

    best_angle = 0.0
    best_var = -1.0
    angles = np.arange(-max_angle, max_angle + step, step)
    for angle in angles:
        rotated = _rotate(binary, angle)
        proj = rotated.sum(axis=1)
        var = float(np.var(proj))
        if var > best_var:
            best_var = var
            best_angle = float(angle)
    return best_angle


def deskew(image: np.ndarray, angle_deg: float) -> np.ndarray:
    if abs(angle_deg) < 1e-3:
        return image
    return _rotate(image, angle_deg, fill=255)


def _rotate(image: np.ndarray, angle_deg: float, fill: int = 0) -> np.ndarray:
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=fill,
    )

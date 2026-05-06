"""Circle / arc fitting.

Algebraic circle fit (Kasa method) with a least-squares refinement step. For
RANSAC we sample triples of points; the algebraic fit on the inliers gives a
more stable result than a 3-point circle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np


Point = Tuple[float, float]


@dataclass
class CircleFit:
    cx: float
    cy: float
    r: float
    rms_px: float
    inliers: int


@dataclass
class ArcFit:
    cx: float
    cy: float
    r: float
    start_angle_deg: float
    end_angle_deg: float
    rms_px: float
    inliers: int


def fit_circle(points: Sequence[Point]) -> CircleFit | None:
    if len(points) < 3:
        return None
    pts = np.asarray(points, dtype=np.float64)
    x, y = pts[:, 0], pts[:, 1]

    # Algebraic Kasa fit: minimise (x²+y²) + Dx + Ey + F = 0.
    A = np.column_stack([x, y, np.ones_like(x)])
    b = -(x ** 2 + y ** 2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol
    cx, cy = -D / 2.0, -E / 2.0
    inside = cx ** 2 + cy ** 2 - F
    if inside <= 0:
        return None
    r = float(np.sqrt(inside))

    rs = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    rms = float(np.sqrt(np.mean((rs - r) ** 2)))
    return CircleFit(cx=float(cx), cy=float(cy), r=r, rms_px=rms, inliers=len(pts))


def detect_circle_or_arc(points: Sequence[Point], *, residual_tol: float = 2.0, min_inliers: int = 30) -> CircleFit | ArcFit | None:
    fit = fit_circle(points)
    if fit is None:
        return None
    if fit.rms_px > residual_tol or fit.inliers < min_inliers:
        return None

    # Estimate angular coverage; if it's near 360°, return a CIRCLE.
    pts = np.asarray(points, dtype=np.float64)
    angles = np.arctan2(pts[:, 1] - fit.cy, pts[:, 0] - fit.cx)
    angles_deg = np.degrees(angles) % 360.0
    coverage = _angular_coverage_deg(angles_deg)
    if coverage > 330.0:
        return fit

    start, end = _arc_endpoints_deg(angles_deg)
    return ArcFit(
        cx=fit.cx, cy=fit.cy, r=fit.r,
        start_angle_deg=start, end_angle_deg=end,
        rms_px=fit.rms_px, inliers=fit.inliers,
    )


def _angular_coverage_deg(angles_deg: np.ndarray) -> float:
    if angles_deg.size == 0:
        return 0.0
    a = np.sort(angles_deg)
    gaps = np.diff(a)
    wrap = 360.0 - (a[-1] - a[0])
    largest_gap = float(max(gaps.max(initial=0.0), wrap))
    return 360.0 - largest_gap


def _arc_endpoints_deg(angles_deg: np.ndarray) -> tuple[float, float]:
    a = np.sort(angles_deg)
    gaps = np.diff(a)
    wrap = 360.0 - (a[-1] - a[0])
    if wrap > gaps.max(initial=0.0):
        # the largest gap is the wrap gap → arc is contiguous in [a[0], a[-1]]
        return float(a[0]), float(a[-1])
    idx = int(np.argmax(gaps))
    # arc goes from a[idx+1] forward through 360 back to a[idx]
    return float(a[idx + 1]), float(a[idx])

"""Compute IoU + chamfer + Hausdorff between two binary rasters."""
from __future__ import annotations

import cv2
import numpy as np


def raster_iou(a: np.ndarray, b: np.ndarray) -> float:
    a_b = a > 0
    b_b = b > 0
    inter = np.logical_and(a_b, b_b).sum()
    union = np.logical_or(a_b, b_b).sum()
    if union == 0:
        return 1.0
    return float(inter / union)


def chamfer_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Mean over points-of-A of the distance to the nearest point-of-B (and
    symmetric average). Uses cv2.distanceTransform on the inverted target."""
    if not (a > 0).any() or not (b > 0).any():
        return float("inf")
    inv_b = (b == 0).astype(np.uint8)
    inv_a = (a == 0).astype(np.uint8)
    dt_b = cv2.distanceTransform(inv_b, cv2.DIST_L2, 3)
    dt_a = cv2.distanceTransform(inv_a, cv2.DIST_L2, 3)

    a_b = a > 0
    b_b = b > 0
    d1 = float(dt_b[a_b].mean()) if a_b.any() else 0.0
    d2 = float(dt_a[b_b].mean()) if b_b.any() else 0.0
    return (d1 + d2) / 2.0


def hausdorff_distance(a: np.ndarray, b: np.ndarray, *, percentile: float = 99.0) -> float:
    """95th-/99th-percentile Hausdorff distance — robust to outliers."""
    if not (a > 0).any() or not (b > 0).any():
        return float("inf")
    inv_b = (b == 0).astype(np.uint8)
    inv_a = (a == 0).astype(np.uint8)
    dt_b = cv2.distanceTransform(inv_b, cv2.DIST_L2, 3)
    dt_a = cv2.distanceTransform(inv_a, cv2.DIST_L2, 3)

    a_pts = dt_b[a > 0]
    b_pts = dt_a[b > 0]
    if a_pts.size == 0 or b_pts.size == 0:
        return float("inf")
    d1 = float(np.percentile(a_pts, percentile))
    d2 = float(np.percentile(b_pts, percentile))
    return max(d1, d2)


def heatmap(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """A diagnostic image: the chamfer distance from each ink pixel of `a`
    to the nearest pixel of `b`. Visualised as a colormap PNG."""
    inv_b = (b == 0).astype(np.uint8)
    dt_b = cv2.distanceTransform(inv_b, cv2.DIST_L2, 3)
    h = np.zeros_like(dt_b, dtype=np.uint8)
    a_b = a > 0
    if a_b.any():
        vals = dt_b[a_b]
        norm = np.clip(vals / max(1.0, np.percentile(vals, 99)), 0.0, 1.0)
        h[a_b] = (norm * 255).astype(np.uint8)
    return cv2.applyColorMap(h, cv2.COLORMAP_INFERNO)

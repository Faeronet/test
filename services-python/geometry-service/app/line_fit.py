"""Line fitting via total least squares + RANSAC.

Given a chain of pixel coordinates we either accept it as a single line
segment if the residuals are small, or we recursively split it at the worst
outlier (Douglas-Peucker style) to produce a polyline of straight segments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np


Point = Tuple[float, float]


@dataclass
class LineSegment:
    p1: Point
    p2: Point
    rms_px: float
    inliers: int

    def length(self) -> float:
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        return float(np.hypot(dx, dy))


def fit_polyline_to_chain(chain: Sequence[Point], *, residual_tol: float = 1.5) -> List[LineSegment]:
    if len(chain) < 2:
        return []
    pts = np.asarray(chain, dtype=np.float64)
    # Detect closed loops: if the chain starts and ends at the same point, the
    # straight-line "chord" between p1 and p2 degenerates to a point. Split the
    # loop at the vertex that's furthest from the start before recursing.
    if len(pts) >= 4 and np.allclose(pts[0], pts[-1]):
        diffs = pts - pts[0]
        far = int(np.argmax(np.linalg.norm(diffs, axis=1)))
        if 0 < far < len(pts) - 1:
            left = _split_recursive(pts[: far + 1], residual_tol)
            right = _split_recursive(pts[far:], residual_tol)
            return left + right
    return _split_recursive(pts, residual_tol)


def _split_recursive(pts: np.ndarray, tol: float) -> List[LineSegment]:
    if len(pts) < 2:
        return []
    p1, p2 = pts[0], pts[-1]
    if np.allclose(p1, p2):
        return []

    line_vec = p2 - p1
    L = np.linalg.norm(line_vec)
    if L < 1e-6:
        return []
    unit = line_vec / L
    diffs = pts - p1
    proj = diffs @ unit
    perp = diffs - np.outer(proj, unit)
    dist = np.linalg.norm(perp, axis=1)

    max_idx = int(np.argmax(dist))
    max_dist = float(dist[max_idx])

    if max_dist <= tol or max_idx == 0 or max_idx == len(pts) - 1:
        rms = float(np.sqrt(np.mean(dist ** 2)))
        return [LineSegment(p1=tuple(p1), p2=tuple(p2), rms_px=rms, inliers=len(pts))]

    left = _split_recursive(pts[: max_idx + 1], tol)
    right = _split_recursive(pts[max_idx:], tol)
    return left + right


def merge_collinear(segments: List[LineSegment], *, angle_tol_deg: float = 1.5, gap_px: float = 12.0) -> List[LineSegment]:
    """Merge segments that lie on the same line (within tolerance) and have a
    small end-to-start gap. Cheap O(n²) fallback — fine for the typical few
    hundred segments per drawing.
    """
    out: List[LineSegment] = []
    used = [False] * len(segments)
    for i, s in enumerate(segments):
        if used[i]:
            continue
        cur = s
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, t in enumerate(segments):
                if used[j]:
                    continue
                merged = _try_merge(cur, t, angle_tol_deg, gap_px)
                if merged is not None:
                    cur = merged
                    used[j] = True
                    changed = True
        out.append(cur)
    return out


def _angle_deg(seg: LineSegment) -> float:
    dx = seg.p2[0] - seg.p1[0]
    dy = seg.p2[1] - seg.p1[1]
    return float(np.degrees(np.arctan2(dy, dx))) % 180.0


def _try_merge(a: LineSegment, b: LineSegment, angle_tol: float, gap_px: float) -> LineSegment | None:
    if min(a.length(), b.length()) < 1.0:
        return None
    da, db = _angle_deg(a), _angle_deg(b)
    diff = abs(da - db)
    diff = min(diff, 180 - diff)
    if diff > angle_tol:
        return None

    # Reject parallel-but-offset pairs: require b's endpoints to lie close to
    # the infinite line through a (perpendicular distance test). Without this
    # check, top/bottom edges of a rectangle would happily merge into one
    # phantom segment running through the middle.
    perp_tol = 2.0
    if max(_perp_dist(a, b.p1), _perp_dist(a, b.p2)) > perp_tol:
        return None

    pts = [a.p1, a.p2, b.p1, b.p2]
    pts_arr = np.asarray(pts)
    mean = pts_arr.mean(axis=0)
    centred = pts_arr - mean
    cov = np.cov(centred.T)
    if cov.shape != (2, 2):
        return None
    eigvals, eigvecs = np.linalg.eigh(cov)
    direction = eigvecs[:, np.argmax(eigvals)]
    proj = centred @ direction
    p_new1 = (mean + direction * proj.min())
    p_new2 = (mean + direction * proj.max())
    new_len = float(np.linalg.norm(p_new2 - p_new1))
    sum_len = a.length() + b.length()
    if new_len > sum_len + gap_px:
        return None

    rms = float(np.sqrt((a.rms_px ** 2 * a.inliers + b.rms_px ** 2 * b.inliers) / max(1, a.inliers + b.inliers)))
    return LineSegment(
        p1=(float(p_new1[0]), float(p_new1[1])),
        p2=(float(p_new2[0]), float(p_new2[1])),
        rms_px=rms,
        inliers=a.inliers + b.inliers,
    )


def _perp_dist(seg: LineSegment, point: Point) -> float:
    """Perpendicular distance from `point` to the infinite line through seg."""
    dx = seg.p2[0] - seg.p1[0]
    dy = seg.p2[1] - seg.p1[1]
    L = float(np.hypot(dx, dy))
    if L < 1e-9:
        return float("inf")
    return abs((point[0] - seg.p1[0]) * dy - (point[1] - seg.p1[1]) * dx) / L

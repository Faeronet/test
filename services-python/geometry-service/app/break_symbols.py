"""Helpers for handling break symbols (zig-zag / wave conventions used to
denote a foreshortened part of a long object)."""
from __future__ import annotations

from typing import List

import numpy as np

from .line_fit import LineSegment


def enforce_collinear_around_break(
    segments: List[LineSegment],
    break_centers: List[tuple[float, float]],
    *,
    radius_px: float = 25.0,
) -> List[LineSegment]:
    """For every break-symbol centre, find the two longest segments that pass
    near it and align them to the same axis. We keep the resulting segments
    on the geometry layer; the actual break wave is rendered separately on
    the break-symbols layer.
    """
    if not segments or not break_centers:
        return segments
    pts = np.asarray(break_centers, dtype=np.float64)
    seg_arr = np.asarray([(s.p1[0], s.p1[1], s.p2[0], s.p2[1]) for s in segments])

    out = list(segments)
    for cx, cy in pts:
        # distance from segment to point.
        dist = _segment_point_distance(seg_arr, np.array([cx, cy]))
        idxs = np.argsort(dist)[:2]
        if len(idxs) < 2:
            continue
        a, b = out[int(idxs[0])], out[int(idxs[1])]
        # Skip if either segment is more than radius_px away.
        if dist[idxs].max() > radius_px:
            continue
        # Force same orientation as the longer segment.
        primary = a if a.length() >= b.length() else b
        out[int(idxs[0])], out[int(idxs[1])] = _align(primary, a), _align(primary, b)
    return out


def _segment_point_distance(seg_arr: np.ndarray, p: np.ndarray) -> np.ndarray:
    p1 = seg_arr[:, :2]
    p2 = seg_arr[:, 2:]
    v = p2 - p1
    L2 = (v ** 2).sum(axis=1)
    L2 = np.where(L2 < 1e-9, 1.0, L2)
    t = ((p - p1) * v).sum(axis=1) / L2
    t = np.clip(t, 0.0, 1.0)
    closest = p1 + (v.T * t).T
    return np.linalg.norm(closest - p, axis=1)


def _align(target: LineSegment, seg: LineSegment) -> LineSegment:
    """Rotate ``seg`` around its midpoint so that its direction matches
    ``target``."""
    tdx = target.p2[0] - target.p1[0]
    tdy = target.p2[1] - target.p1[1]
    tlen = float(np.hypot(tdx, tdy)) or 1.0
    ux, uy = tdx / tlen, tdy / tlen

    mid = ((seg.p1[0] + seg.p2[0]) / 2.0, (seg.p1[1] + seg.p2[1]) / 2.0)
    half = seg.length() / 2.0
    return LineSegment(
        p1=(mid[0] - ux * half, mid[1] - uy * half),
        p2=(mid[0] + ux * half, mid[1] + uy * half),
        rms_px=seg.rms_px,
        inliers=seg.inliers,
    )

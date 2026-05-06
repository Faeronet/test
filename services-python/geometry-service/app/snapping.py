"""Endpoint and angle snapping.

* Snap line endpoints that are within ``endpoint_tolerance_px`` to a shared
  point. Implemented with a simple grid bucket (no scipy KD-tree needed).
* Snap line angles to one of the configured snap angles (default 0/45/90/135)
  if within ``angle_tolerance_deg``.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

import numpy as np

from .line_fit import LineSegment


def snap_angles(segments: List[LineSegment], *, snap_angles_deg: Sequence[float] = (0.0, 45.0, 90.0, 135.0), tolerance_deg: float = 1.5) -> List[LineSegment]:
    out: List[LineSegment] = []
    for s in segments:
        dx = s.p2[0] - s.p1[0]
        dy = s.p2[1] - s.p1[1]
        if abs(dx) + abs(dy) < 1e-6:
            out.append(s)
            continue
        angle = (np.degrees(np.arctan2(dy, dx)) + 360.0) % 180.0
        best = min(snap_angles_deg, key=lambda a: min(abs(angle - a), 180 - abs(angle - a)))
        diff = min(abs(angle - best), 180 - abs(angle - best))
        if diff > tolerance_deg:
            out.append(s)
            continue
        # Rotate the segment around its midpoint to the snapped angle.
        mid = ((s.p1[0] + s.p2[0]) / 2.0, (s.p1[1] + s.p2[1]) / 2.0)
        length = float(np.hypot(dx, dy))
        rad = np.radians(best)
        nx = float(np.cos(rad)) * length / 2.0
        ny = float(np.sin(rad)) * length / 2.0
        out.append(
            LineSegment(
                p1=(mid[0] - nx, mid[1] - ny),
                p2=(mid[0] + nx, mid[1] + ny),
                rms_px=s.rms_px,
                inliers=s.inliers,
            )
        )
    return out


def snap_endpoints(segments: List[LineSegment], *, tolerance_px: float = 4.0) -> List[LineSegment]:
    if not segments:
        return segments
    pts = []
    for s in segments:
        pts.append(s.p1)
        pts.append(s.p2)

    arr = np.asarray(pts, dtype=np.float64)
    visited = [False] * len(pts)
    canonical = list(range(len(pts)))
    for i, p in enumerate(arr):
        if visited[i]:
            continue
        # find all points within tolerance
        d = np.linalg.norm(arr - p, axis=1)
        ids = np.where(d <= tolerance_px)[0]
        for j in ids:
            canonical[int(j)] = i
            visited[int(j)] = True

    new_pts = arr.copy()
    for i in range(len(pts)):
        c = canonical[i]
        if c != i:
            # average endpoints of cluster
            cluster = [j for j in range(len(pts)) if canonical[j] == c]
            avg = arr[cluster].mean(axis=0)
            new_pts[i] = avg

    out: List[LineSegment] = []
    for k, s in enumerate(segments):
        p1 = tuple(new_pts[2 * k])
        p2 = tuple(new_pts[2 * k + 1])
        out.append(LineSegment(p1=p1, p2=p2, rms_px=s.rms_px, inliers=s.inliers))
    return out


def chunked(seq: Iterable, size: int):  # noqa: D401
    """Tiny helper kept for symmetry with C++ port plans."""
    chunk: list = []
    for item in seq:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

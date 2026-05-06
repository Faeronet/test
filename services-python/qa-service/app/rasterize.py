"""Rasterise CAD JSON primitives into a binary mask matching the source page.

Used by the QA service to compare against the binarised input via raster IoU,
chamfer distance and Hausdorff distance.
"""
from __future__ import annotations

from typing import Iterable, Tuple

import cv2
import numpy as np


def rasterise(primitives: Iterable[dict], size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    canvas = np.zeros((h, w), dtype=np.uint8)
    for p in primitives:
        layer = p.get("layer", "")
        if layer == "99_RASTER_REFERENCE":
            continue
        t = p.get("type")
        if t == "LINE":
            p1 = p.get("p1") or [0, 0]
            p2 = p.get("p2") or [0, 0]
            cv2.line(canvas, _i(p1), _i(p2), 255, 2)
        elif t == "CIRCLE":
            c = p.get("center") or [0, 0]
            r = int(round(p.get("radius", 0)))
            if r > 0:
                cv2.circle(canvas, _i(c), r, 255, 2)
        elif t == "ARC":
            c = p.get("center") or [0, 0]
            r = int(round(p.get("radius", 0)))
            sa = float(p.get("start_angle_deg", 0))
            ea = float(p.get("end_angle_deg", 360))
            if r > 0:
                cv2.ellipse(canvas, _i(c), (r, r), 0.0, sa, ea, 255, 2)
        elif t == "LWPOLYLINE":
            pts = p.get("vertices") or []
            if len(pts) >= 2:
                arr = np.array([_i(v) for v in pts], dtype=np.int32)
                cv2.polylines(canvas, [arr], bool(p.get("closed")), 255, 2)
    return canvas


def _i(p) -> tuple[int, int]:
    return int(round(float(p[0]))), int(round(float(p[1])))

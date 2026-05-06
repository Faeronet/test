"""Identify the outer drawing frame (a large rectangle near the page edges)
and provide a *non-destructive* crop suggestion. We do NOT actually crop the
raster: cropping changes the page coordinate system that the user expects.
The downstream geometry stage uses the inner-rect mask only to ignore
frame/titleblock pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class FrameInfo:
    inner_bbox: Tuple[int, int, int, int]  # x1,y1,x2,y2 in pixels
    found: bool


def detect_frame(binary: np.ndarray) -> FrameInfo:
    """Returns the largest rectangle near the page border. Falls back to the
    full image bounds when nothing convincing is found.
    """
    h, w = binary.shape[:2]
    full = (0, 0, w, h)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return FrameInfo(inner_bbox=full, found=False)

    page_area = h * w
    best = None
    best_area = 0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        if area < 0.4 * page_area:
            continue
        if area > best_area:
            best_area = area
            best = (x, y, x + cw, y + ch)

    if best is None:
        return FrameInfo(inner_bbox=full, found=False)
    return FrameInfo(inner_bbox=best, found=True)

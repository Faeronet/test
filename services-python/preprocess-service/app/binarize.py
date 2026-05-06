"""Binarisation step: convert grayscale to a clean black-on-white binary mask
suitable for downstream skeletonisation.

`binarize` returns a uint8 image with 0 = background, 255 = foreground (the
ink). We invert at the end if needed so that downstream code can rely on the
same convention regardless of the source.
"""
from __future__ import annotations

import cv2
import numpy as np


def binarize(gray: np.ndarray, method: str = "adaptive") -> np.ndarray:
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    if method == "otsu":
        _, bin_img = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        bin_img = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )

    # We want foreground = ink = 255. Heuristic: if mean is > 127, foreground
    # is currently dark, so invert.
    if bin_img.mean() > 127:
        bin_img = cv2.bitwise_not(bin_img)
    return bin_img

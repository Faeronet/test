"""Skeletonisation / thinning utilities.

We rely on ``skimage.morphology.skeletonize`` (Zhang-Suen variant) which is
robust to small notches and reasonably fast on CPU. Foreground convention:
255 = ink.
"""
from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize


def skeletonise(binary: np.ndarray) -> np.ndarray:
    if binary.ndim == 3:
        binary = cv2.cvtColor(binary, cv2.COLOR_BGR2GRAY)
    if binary.dtype != np.uint8:
        binary = binary.astype(np.uint8)
    bool_img = binary > 0
    skel = skeletonize(bool_img)
    return (skel.astype(np.uint8) * 255)

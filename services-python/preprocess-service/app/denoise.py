"""Light denoising and contrast normalisation."""
from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray, strength: int = 7) -> np.ndarray:
    return cv2.fastNlMeansDenoising(gray, h=strength, templateWindowSize=7, searchWindowSize=21)


def normalise_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    return clahe.apply(gray)


def estimate_noise_score(gray: np.ndarray) -> float:
    """Standard deviation of Laplacian — lower means noisier images, scaled to [0,1]."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = float(lap.var())
    return float(min(1.0, var / 1500.0))


def estimate_contrast_score(gray: np.ndarray) -> float:
    return float(np.clip(gray.std() / 80.0, 0.0, 1.0))

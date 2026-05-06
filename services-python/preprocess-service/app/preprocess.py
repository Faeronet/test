"""End-to-end preprocessing pipeline that turns a raw page raster into:

  - a normalised grayscale image (`normalized.png`)
  - a binary mask                  (`binary.png`)
  - a downscaled preview           (`preview.jpg`)
  - a quality / metadata blob

It works on numpy arrays in-memory and returns bytes for every artifact, so
the orchestrator can upload them to MinIO without touching disk.
"""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass

import cv2
import numpy as np
from PIL import Image

from .binarize import binarize
from .denoise import denoise, normalise_contrast, to_grayscale
from .deskew import deskew, estimate_skew_deg
from .frame_crop import detect_frame
from .quality import QualityReport, estimate_quality


@dataclass
class PreprocessResult:
    normalized_png: bytes
    binary_png: bytes
    preview_jpg: bytes
    width: int
    height: int
    quality: QualityReport
    inner_bbox: tuple[int, int, int, int]

    def metadata(self) -> dict:
        return {
            "width_px": self.width,
            "height_px": self.height,
            "quality": {
                **{k: v for k, v in asdict(self.quality).items() if k != "warnings"},
                "warnings": self.quality.warnings,
            },
            "inner_bbox": list(self.inner_bbox),
        }


def preprocess_page(image_bytes: bytes, *, deskew_enabled: bool = True, max_preview_side: int = 1600) -> PreprocessResult:
    img = _decode(image_bytes)
    if img is None:
        raise ValueError("could not decode page image")
    h, w = img.shape[:2]

    gray = to_grayscale(img)
    gray = normalise_contrast(gray)
    gray = denoise(gray, strength=7)

    bin_img = binarize(gray, method="adaptive")

    skew_deg = estimate_skew_deg(bin_img) if deskew_enabled else 0.0
    if abs(skew_deg) >= 0.2:
        gray = deskew(gray, skew_deg)
        bin_img = deskew(bin_img, skew_deg)

    frame = detect_frame(bin_img)

    quality = estimate_quality(gray, bin_img, skew_deg)

    return PreprocessResult(
        normalized_png=_encode_png(gray),
        binary_png=_encode_png(bin_img),
        preview_jpg=_encode_preview_jpg(gray, max_preview_side),
        width=w,
        height=h,
        quality=quality,
        inner_bbox=frame.inner_bbox,
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _decode(image_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is not None:
        return img
    # Fallback to PIL for TIFF / WEBP corner cases.
    try:
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            pil_img.load()
            if pil_img.mode not in ("RGB", "L"):
                pil_img = pil_img.convert("RGB")
            arr = np.asarray(pil_img)
            if arr.ndim == 3:
                return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr
    except Exception:  # noqa: BLE001
        return None


def _encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise RuntimeError("png encoding failed")
    return buf.tobytes()


def _encode_preview_jpg(gray: np.ndarray, max_side: int = 1600) -> bytes:
    h, w = gray.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1.0:
        gray = cv2.resize(gray, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("jpeg encoding failed")
    return buf.tobytes()

"""Rule-based page classifier.

Heuristics:

* If the page is mostly composed of small text-like blobs arranged in a tight
  grid, label it ``specification_sheet``.
* If the page is too dark, too blank, or strongly noisy, label ``bad_scan``.
* Otherwise label ``detail_drawing`` (we don't try to distinguish detail vs
  assembly from rules alone — the YOLO11s-cls model will).

This is intentionally conservative: when in doubt, we return ``unknown`` so
the human reviewer is engaged.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from .page_router import PageRouter, RouterResult


class MockRouter(PageRouter):
    def __init__(
        self,
        *,
        text_density_specification_threshold: float = 0.45,
        table_grid_min_cells: int = 18,
        bad_scan_min_quality: float = 0.25,
    ) -> None:
        self.text_density_specification_threshold = text_density_specification_threshold
        self.table_grid_min_cells = table_grid_min_cells
        self.bad_scan_min_quality = bad_scan_min_quality

    def classify(self, image: bytes, *, preview: bytes | None = None) -> RouterResult:
        gray = self._decode_gray(image)
        if gray is None:
            return RouterResult("unknown", 0.0, "decode_failed", "rules-v1")

        h, w = gray.shape[:2]
        if h * w == 0:
            return RouterResult("unknown", 0.0, "empty_image", "rules-v1")

        # binarise (foreground=255)
        bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        if bin_img.mean() > 127:
            bin_img = cv2.bitwise_not(bin_img)
        fg_ratio = float(np.count_nonzero(bin_img) / (h * w))

        contrast = float(np.clip(gray.std() / 80.0, 0.0, 1.0))
        if contrast < self.bad_scan_min_quality and fg_ratio < 0.005:
            return RouterResult("bad_scan", 0.85, "low_contrast_blank", "rules-v1")
        if fg_ratio > 0.8:
            return RouterResult("bad_scan", 0.7, "almost_solid_page", "rules-v1")

        text_density, grid_cells = self._table_metrics(bin_img)

        if text_density >= self.text_density_specification_threshold and grid_cells >= self.table_grid_min_cells:
            return RouterResult(
                page_type="specification_sheet",
                confidence=float(min(0.95, 0.5 + 0.5 * text_density)),
                reason=f"high_text_density_with_grid:density={text_density:.2f},cells={grid_cells}",
                model_version="rules-v1",
            )

        if text_density < 0.15 and grid_cells < 4:
            return RouterResult(
                page_type="detail_drawing",
                confidence=float(min(0.85, 0.55 + 0.5 * (1 - text_density))),
                reason=f"low_text_density:density={text_density:.2f}",
                model_version="rules-v1",
            )

        return RouterResult(
            page_type="unknown",
            confidence=0.4,
            reason=f"ambiguous:density={text_density:.2f},cells={grid_cells}",
            model_version="rules-v1",
        )

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _decode_gray(b: bytes) -> np.ndarray | None:
        arr = np.frombuffer(b, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img
        try:
            with Image.open(io.BytesIO(b)) as pil:
                pil.load()
                return np.asarray(pil.convert("L"))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _table_metrics(bin_img: np.ndarray) -> tuple[float, int]:
        h, w = bin_img.shape[:2]

        num, _, stats, _ = cv2.connectedComponentsWithStats(bin_img, connectivity=8)
        small = 0
        for i in range(1, num):
            a = int(stats[i, cv2.CC_STAT_AREA])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            if a <= 0:
                continue
            if 8 <= a <= 800 and 3 <= bw <= 80 and 3 <= bh <= 80:
                small += 1
        density = float(min(1.0, small / max(1.0, (h * w) / 40_000)))

        # Grid heuristic: count the number of long horizontal/vertical lines
        # which intersect to form table cells.
        horiz = cv2.morphologyEx(
            bin_img, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, w // 30), 1))
        )
        vert = cv2.morphologyEx(
            bin_img, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, h // 30)))
        )
        grid = cv2.bitwise_and(horiz, vert)
        cells = int(cv2.connectedComponents(grid)[0]) - 1
        return density, max(0, cells)

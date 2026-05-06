"""Classical computer-vision fallback that produces the same mask classes as
the future YOLO11m-seg model.

Strategy
========
We start from the binarised foreground produced by preprocess-service. We
then try to peel off, in order:

1. ``frame_titleblock``  — the largest near-rectangular outline along the
   page edges (and the dense cell-grid attached to it, typical of a КОМПАС
   frame + штамп).
2. ``hatch``              — repeating diagonal/horizontal stripe regions.
3. ``text``               — small connected components grouped into rows.
4. ``dimension_graphics`` — long thin runs ending with arrowheads (cheap
   approximation: thin small components near rows of text).
5. ``centerline``         — long thin geometry whose pixel pattern matches
   the standard КОМПАС dash-dot stride.
6. ``break_symbol``       — wave-like / zig-zag contours.
7. ``visible_geometry``   — whatever remains.
8. ``noise``              — speckle (very small components removed in a
   morphological cleanup step).

We deliberately keep confidences modest — these are heuristics. The geometry
service treats them as soft signals, not hard labels.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from .masks import CLASSES, Mask, MaskBundle


class MockSegmenter:
    def __init__(self) -> None:
        pass

    def segment(self, normalized_image: bytes, *, binary_image: bytes | None = None) -> MaskBundle:
        gray = self._decode_gray(normalized_image)
        if gray is None:
            raise ValueError("could not decode normalised image")

        if binary_image:
            bin_img = self._decode_gray(binary_image)
        else:
            bin_img = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
            )
            if bin_img.mean() > 127:
                bin_img = cv2.bitwise_not(bin_img)

        h, w = bin_img.shape[:2]

        masks: dict[str, Mask] = {}

        frame_mask = self._frame_titleblock(bin_img)
        masks["frame_titleblock"] = self._pack(frame_mask, conf=0.5)

        # Remove frame from the working copy so subsequent stages don't pick it up.
        working = cv2.bitwise_and(bin_img, cv2.bitwise_not(frame_mask))

        hatch_mask = self._hatch(working)
        masks["hatch"] = self._pack(hatch_mask, conf=0.4)
        working = cv2.bitwise_and(working, cv2.bitwise_not(hatch_mask))

        text_mask = self._text(working)
        masks["text"] = self._pack(text_mask, conf=0.45)

        dim_mask = self._dimension_graphics(working, text_mask)
        masks["dimension_graphics"] = self._pack(dim_mask, conf=0.4)

        center_mask = self._centerline(working)
        masks["centerline"] = self._pack(center_mask, conf=0.35)

        break_mask = self._break_symbol(working)
        masks["break_symbol"] = self._pack(break_mask, conf=0.3)

        # noise: small isolated components left in the background
        noise_mask = self._noise(working)
        masks["noise"] = self._pack(noise_mask, conf=0.5)

        # visible geometry = working minus everything we have peeled off
        peeled = cv2.bitwise_or(text_mask, dim_mask)
        peeled = cv2.bitwise_or(peeled, center_mask)
        peeled = cv2.bitwise_or(peeled, break_mask)
        peeled = cv2.bitwise_or(peeled, noise_mask)
        visible = cv2.bitwise_and(working, cv2.bitwise_not(peeled))
        masks["visible_geometry"] = self._pack(visible, conf=0.55)

        # placeholders for classes we cannot reasonably synthesise without ML.
        empty = np.zeros((h, w), dtype=np.uint8)
        masks["hidden_geometry"] = self._pack(empty, conf=0.0)
        masks["stamp_signature"] = self._pack(empty, conf=0.0)

        return MaskBundle(masks=masks, width=w, height=h, model_version="classical-v1")

    # ── stages ────────────────────────────────────────────────────────

    @staticmethod
    def _frame_titleblock(bin_img: np.ndarray) -> np.ndarray:
        h, w = bin_img.shape[:2]
        contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result = np.zeros_like(bin_img)
        if not contours:
            return result
        page_area = h * w
        best = None
        best_area = 0
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if cw * ch < 0.4 * page_area:
                continue
            if cw * ch > best_area:
                best_area = cw * ch
                best = c
        if best is None:
            return result
        # Draw the contour with thickness so neighbouring grid lines get included.
        cv2.drawContours(result, [best], -1, color=255, thickness=max(2, int(min(h, w) / 600)))
        return result

    @staticmethod
    def _hatch(bin_img: np.ndarray) -> np.ndarray:
        # Detect dense diagonal stripe regions by morphological top-hat with
        # rotated kernels. Cheap approximation; do not aim for perfection.
        h, w = bin_img.shape[:2]
        results = []
        for angle in (45, -45, 0):
            ksize = max(15, min(h, w) // 80)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, 1))
            kernel = MockSegmenter._rotate_kernel(kernel, angle)
            top = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, kernel)
            results.append(top)
        return cv2.bitwise_and(*results[:2])

    @staticmethod
    def _text(bin_img: np.ndarray) -> np.ndarray:
        h, w = bin_img.shape[:2]
        out = np.zeros_like(bin_img)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(bin_img, connectivity=8)
        for i in range(1, num):
            a = int(stats[i, cv2.CC_STAT_AREA])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            if a <= 0:
                continue
            if 8 <= a <= 800 and 3 <= bw <= 80 and 3 <= bh <= 80:
                out[labels == i] = 255
        # Dilate slightly to merge characters into words/rows.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 400), max(2, h // 600)))
        return cv2.dilate(out, kernel, iterations=1)

    @staticmethod
    def _dimension_graphics(bin_img: np.ndarray, text_mask: np.ndarray) -> np.ndarray:
        # Treat thin linear runs that touch text rows as dimension graphics.
        h, w = bin_img.shape[:2]
        thin = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 50), 1)))
        thin |= cv2.morphologyEx(bin_img, cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 50))))
        # AND with neighbourhood of text to bias toward dimension lines.
        text_dilated = cv2.dilate(text_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 30), max(20, h // 30))))
        return cv2.bitwise_and(thin, text_dilated)

    @staticmethod
    def _centerline(bin_img: np.ndarray) -> np.ndarray:
        # Centerlines are dash-dot patterns. We approximate by detecting long
        # collinear runs of small components.
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        eroded_h = cv2.erode(bin_img, kernel_h, iterations=1)
        eroded_v = cv2.erode(bin_img, kernel_v, iterations=1)
        dashes = cv2.bitwise_or(eroded_h, eroded_v)
        return cv2.dilate(dashes, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    @staticmethod
    def _break_symbol(bin_img: np.ndarray) -> np.ndarray:
        # Heuristic placeholder: small zig-zag contours have aspect ratio near 1
        # and high perimeter/area ratio. We approximate by rejecting everything
        # except contours with very high perimeter² / area inside a thin band.
        out = np.zeros_like(bin_img)
        contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in contours:
            a = cv2.contourArea(c)
            p = cv2.arcLength(c, True)
            if a <= 0:
                continue
            ratio = (p * p) / a
            x, y, w, h = cv2.boundingRect(c)
            ar = w / max(1.0, h)
            if ratio > 80 and 2 <= ar <= 12:
                cv2.drawContours(out, [c], -1, 255, thickness=cv2.FILLED)
        return out

    @staticmethod
    def _noise(bin_img: np.ndarray) -> np.ndarray:
        out = np.zeros_like(bin_img)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(bin_img, connectivity=8)
        for i in range(1, num):
            a = int(stats[i, cv2.CC_STAT_AREA])
            if 0 < a < 6:
                out[labels == i] = 255
        return out

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _rotate_kernel(kernel: np.ndarray, angle: float) -> np.ndarray:
        h, w = kernel.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(kernel, M, (w, h), flags=cv2.INTER_NEAREST)

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
    def _pack(mask: np.ndarray, *, conf: float) -> Mask:
        # ensure 0/255
        mask = (mask > 0).astype(np.uint8) * 255
        ok, buf = cv2.imencode(".png", mask, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise RuntimeError("png encoding failed")
        bbox = MockSegmenter._bbox(mask)
        return Mask(png_bytes=buf.tobytes(), confidence=float(conf), bbox=bbox)

    @staticmethod
    def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
        ys, xs = np.where(mask > 0)
        if xs.size == 0:
            return None
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

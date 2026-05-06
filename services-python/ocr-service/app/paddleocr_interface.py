"""Placeholder for PaddleOCR PP-OCRv5 integration.

The trained / fine-tuned PaddleOCR weights are kept under
``$OCR_WEIGHTS_DIR``. The directory layout expected by PaddleOCR is:

    $OCR_WEIGHTS_DIR/
        ch_PP-OCRv5_det/
        ch_PP-OCRv5_rec/
        cls/

When weights are present we instantiate ``paddleocr.PaddleOCR`` with
``use_gpu=ENABLE_GPU``. When they are missing we raise ``FileNotFoundError``
and the service falls back to the mock.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List


class PaddleOCRBackend:
    def __init__(self, weights_dir: str, *, languages: List[str] | None = None, use_gpu: bool = False) -> None:
        self.weights_dir = weights_dir
        self.languages = languages or ["ru", "en"]
        self.use_gpu = use_gpu
        self._engine = None

    @classmethod
    def from_env(cls) -> "PaddleOCRBackend":
        d = os.getenv("OCR_WEIGHTS_DIR", "/models/paddleocr-pp-ocrv5")
        if not Path(d).is_dir():
            raise FileNotFoundError(f"paddleocr weights dir missing: {d}")
        gpu = os.getenv("ENABLE_GPU", "false").lower() in ("1", "true", "yes")
        return cls(weights_dir=d, use_gpu=gpu)

    def detect(self, image: bytes, *, text_mask: bytes | None = None) -> List[dict]:  # pragma: no cover
        # NOTE: implementation deliberately omitted. Wire paddleocr here once
        # the trained weights and dependencies are installed (paddlepaddle +
        # paddleocr packages, plus their CUDA/cudnn stack on GPU).
        raise NotImplementedError("PaddleOCR integration is intentionally stubbed.")

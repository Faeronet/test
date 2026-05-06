"""Placeholder for the future YOLO11m-seg drawing segmenter.

Same conventions as ``yolo_router_interface.py``:

* No automatic weight downloads.
* If weights are missing, raise ``FileNotFoundError`` and let the service
  fall back to the classical implementation.
* When the trained ``.pt`` becomes available, set ``SEG_IMPL=yolo`` and
  point ``SEGMENTATION_WEIGHTS`` at the file.

Implementation TODO:
  - tile-based inference with overlap (see ``configs/models.yaml``)
  - mask post-processing (small-area threshold, multi-class merge)
  - per-class confidence aggregation
"""
from __future__ import annotations

import os
from pathlib import Path

from .masks import MaskBundle


class Yolo11Segmenter:
    def __init__(self, weights_path: str, *, device: str = "cpu", tile_size: int = 1024, tile_overlap: int = 128) -> None:
        self.weights_path = weights_path
        self.device = device
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap

    @classmethod
    def from_env(cls) -> "Yolo11Segmenter":
        path = os.getenv("SEGMENTATION_WEIGHTS", "/models/yolo11m-seg/weights.pt")
        if not Path(path).is_file():
            raise FileNotFoundError(f"segmentation weights not found: {path}")
        device = "cuda" if os.getenv("ENABLE_GPU", "false").lower() in ("1", "true", "yes") else "cpu"
        return cls(weights_path=path, device=device)

    def segment(self, normalized_image: bytes, *, binary_image: bytes | None = None) -> MaskBundle:  # pragma: no cover
        raise NotImplementedError(
            "YOLO11m-seg integration is intentionally stubbed. "
            "Wire ultralytics here when weights are available."
        )

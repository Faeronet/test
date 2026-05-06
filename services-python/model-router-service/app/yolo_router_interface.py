"""Placeholder for the future YOLO11s-cls page router.

This file documents the *contract* that the trained model must satisfy. We do
NOT bundle weights and we do NOT auto-download anything.

When you receive a trained ``weights.pt``:

1. Place it at the path pointed to by ``MODEL_ROUTER_WEIGHTS`` (default
   ``/models/yolo11s-cls/weights.pt``).
2. Set ``ROUTER_IMPL=yolo`` in the environment.
3. Restart this service.

Until then, the service falls back to :class:`MockRouter`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .page_router import PageRouter, RouterResult


CLASSES = (
    "detail_drawing",
    "assembly_drawing",
    "specification_sheet",
    "bad_scan",
    "unknown",
)


class YoloRouter(PageRouter):
    """Lazy-loading YOLO11s-cls wrapper.

    The actual ``ultralytics`` import happens only when the weights file
    exists; this keeps the docker image slim when running in mock mode.
    """

    def __init__(self, weights_path: str, *, image_size: int = 640, device: str = "cpu") -> None:
        self.weights_path = weights_path
        self.image_size = image_size
        self.device = device
        self._model: Optional[object] = None

    @classmethod
    def from_env(cls) -> "YoloRouter":
        path = os.getenv("MODEL_ROUTER_WEIGHTS", "/models/yolo11s-cls/weights.pt")
        device = "cuda" if os.getenv("ENABLE_GPU", "false").lower() in ("1", "true", "yes") else "cpu"
        if not Path(path).is_file():
            raise FileNotFoundError(f"router weights not found: {path}")
        return cls(weights_path=path, device=device)

    def _ensure_loaded(self) -> object:
        if self._model is not None:
            return self._model
        try:  # pragma: no cover — only exercised when weights exist
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ultralytics is not installed in this container; rebuild with the GPU image"
            ) from exc
        self._model = YOLO(self.weights_path)
        return self._model

    def classify(self, image: bytes, *, preview: bytes | None = None) -> RouterResult:  # pragma: no cover
        # NOTE: this code path is exercised only when real weights are mounted.
        import io
        import numpy as np
        from PIL import Image

        model = self._ensure_loaded()
        with Image.open(io.BytesIO(image)) as pil:
            arr = np.asarray(pil.convert("RGB"))

        result = model.predict(arr, imgsz=self.image_size, device=self.device, verbose=False)[0]
        probs = getattr(result, "probs", None)
        if probs is None:
            return RouterResult("unknown", 0.0, "model_returned_no_probs", f"yolo11s-cls@{self.weights_path}")
        top1 = int(probs.top1)
        top1_conf = float(probs.top1conf)
        cls = CLASSES[top1] if 0 <= top1 < len(CLASSES) else "unknown"
        return RouterResult(
            page_type=cls,  # type: ignore[arg-type]
            confidence=top1_conf,
            reason="yolo11s-cls.top1",
            model_version=f"yolo11s-cls@{Path(self.weights_path).name}",
        )

"""Placeholder for the future Qwen2.5-VL review helper.

The VLM is intended to act as a *review helper*, never as the source of CAD
truth. It looks at the source raster + the rendered CAD JSON and explains in
natural language whether the conversion is plausible.

When the trained / fine-tuned weights become available:

1. Drop them under ``$VLM_WEIGHTS_DIR``.
2. Set ``VLM_IMPL=qwen``.
3. Restart this service.

Until then, ``MockVLM`` is used.
"""
from __future__ import annotations

import os
from pathlib import Path


class QwenVLM:
    def __init__(self, weights_dir: str) -> None:
        self.weights_dir = weights_dir

    @classmethod
    def from_env(cls) -> "QwenVLM":
        d = os.getenv("VLM_WEIGHTS_DIR", "/models/qwen2.5-vl")
        if not Path(d).is_dir():
            raise FileNotFoundError(f"qwen weights missing: {d}")
        return cls(weights_dir=d)

    def review(self, cad_json: dict, *, image_uri: str | None = None) -> dict:  # pragma: no cover
        raise NotImplementedError("Qwen2.5-VL integration is intentionally stubbed.")

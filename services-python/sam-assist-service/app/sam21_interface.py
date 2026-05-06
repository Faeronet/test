"""Placeholder for SAM 2.1.

SAM is intended as an *interactive mask assistant* exposed to the reviewer
in the web UI. It is **not** an automatic CAD generator; the geometry
service does not consume its output.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List


class SAM21:
    def __init__(self, weights_path: str) -> None:
        self.weights_path = weights_path

    @classmethod
    def from_env(cls) -> "SAM21":
        path = os.getenv("SAM_WEIGHTS", "/models/sam2.1/weights.pt")
        if not Path(path).is_file():
            raise FileNotFoundError(f"sam weights missing: {path}")
        return cls(weights_path=path)

    def predict_mask(self, *, image_uri: str, points: List[List[float]] | None = None, box: List[float] | None = None) -> dict:  # pragma: no cover
        raise NotImplementedError("SAM 2.1 integration is intentionally stubbed.")

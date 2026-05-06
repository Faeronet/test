"""Mock SAM that simply echoes the bounding box of the user prompt as a
trivial mask. The real SAM 2.1 will replace this when weights are wired in."""
from __future__ import annotations

from typing import List


class MockSAM:
    def predict_mask(self, *, image_uri: str, points: List[List[float]] | None = None, box: List[float] | None = None) -> dict:
        return {
            "ok": True,
            "model_version": "mock-sam",
            "mask_uri": None,
            "note": "MockSAM does not generate real masks; wire SAM 2.1 weights to enable.",
            "echo": {"points": points or [], "box": box or []},
        }

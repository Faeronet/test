"""Mock VLM that produces a deterministic placeholder review."""
from __future__ import annotations

from typing import List


class MockVLM:
    def review(self, cad_json: dict, *, image_uri: str | None = None) -> dict:
        primitives = cad_json.get("primitives", [])
        warnings: List[str] = []
        if not primitives:
            warnings.append("no_primitives")
        else:
            low = sum(1 for p in primitives if (p.get("confidence") or 1.0) < 0.55)
            if low > 0:
                warnings.append(f"{low} primitives have low confidence")
        return {
            "ok": len(warnings) == 0,
            "summary": "Mock VLM review (Qwen2.5-VL is not bundled in MVP).",
            "warnings": warnings,
            "model_version": "mock-vlm",
        }

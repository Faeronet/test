"""Mock OCR backend.

Returns an empty list of OCR blocks. Tests can monkeypatch this class to
return specific synthetic blocks. The dimension_parser is fully functional
even with empty OCR output — the geometry pipeline will fall back to
geometry-only mode.
"""
from __future__ import annotations

from typing import List

from .dimension_parser import parse_dimension


class MockOCR:
    def detect(self, image: bytes, *, text_mask: bytes | None = None) -> List[dict]:
        return []

    @staticmethod
    def parse_string(text: str) -> dict:
        return parse_dimension(text).to_dict()

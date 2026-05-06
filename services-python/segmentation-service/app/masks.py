"""Constants and small helpers around the mask class catalogue.

The class indices below MUST match the trained ``YOLO11m-seg`` model when it
becomes available. The classical fallback emits the same names so downstream
code is agnostic to the implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


CLASSES = (
    "visible_geometry",      # 0
    "hidden_geometry",       # 1
    "centerline",            # 2
    "dimension_graphics",    # 3
    "text",                  # 4
    "hatch",                 # 5
    "break_symbol",          # 6
    "frame_titleblock",      # 7
    "stamp_signature",       # 8
    "noise",                 # 9
)


@dataclass
class MaskBundle:
    """Set of binary masks (uint8, 0/255) keyed by class name."""

    masks: Dict[str, "Mask"]
    width: int
    height: int
    model_version: str

    def to_payload(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "model_version": self.model_version,
            "classes": list(self.masks.keys()),
        }


@dataclass
class Mask:
    png_bytes: bytes        # PNG-encoded mask (binary 0/255)
    confidence: float       # mean confidence over the whole class
    bbox: tuple[int, int, int, int] | None  # x1,y1,x2,y2 of the bounding box, if any

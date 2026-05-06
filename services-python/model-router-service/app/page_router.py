"""Page router contract.

Two implementations live alongside this interface:

- :class:`MockRouter`  — rule-based classifier built on connected components,
  used while we have no trained weights. It is good enough to discard
  specification sheets and obviously bad scans, which is the only hard
  requirement at this stage.
- :class:`YoloRouter`  — placeholder that loads YOLO11s-cls when its weights
  file is present. If the file is missing it raises ``FileNotFoundError`` and
  the service falls back to :class:`MockRouter`.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Literal


PageType = Literal[
    "detail_drawing",
    "assembly_drawing",
    "specification_sheet",
    "bad_scan",
    "unknown",
]


@dataclass
class RouterResult:
    page_type: PageType
    confidence: float
    reason: str
    model_version: str

    def to_payload(self) -> dict:
        return {
            "page_type": self.page_type,
            "confidence": float(self.confidence),
            "reason": self.reason,
            "model_version": self.model_version,
        }


class PageRouter(abc.ABC):
    @abc.abstractmethod
    def classify(self, image: bytes, *, preview: bytes | None = None) -> RouterResult:
        """Classify a page.

        ``image`` is the normalised grayscale PNG from the preprocess stage
        (full resolution). ``preview`` is the optional downscaled preview.
        """


__all__ = ["PageRouter", "RouterResult", "PageType"]

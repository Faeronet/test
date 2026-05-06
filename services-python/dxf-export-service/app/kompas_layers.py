"""Layer catalogue + colour mapping tuned for КОМПАС-3D import."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LayerSpec:
    name: str
    color: int   # AutoCAD color index (ACI)
    role: str
    linetype: str = "CONTINUOUS"


# Order matters — DXF requires the layer table to be complete before any
# entities are added.
LAYERS: List[LayerSpec] = [
    LayerSpec("00_FRAME",              color=8, role="frame"),
    LayerSpec("01_TITLE_BLOCK",        color=8, role="titleblock"),
    LayerSpec("02_PART_VISIBLE",       color=7, role="geometry"),
    LayerSpec("03_PART_HIDDEN",        color=5, role="hidden",     linetype="DASHED"),
    LayerSpec("04_CENTER_AXIS",        color=1, role="centerline", linetype="CENTER"),
    LayerSpec("05_DIM_LINES",          color=3, role="dimension"),
    LayerSpec("06_DIM_TEXT",           color=3, role="dimension_text"),
    LayerSpec("07_TEXT_NOTES",         color=7, role="text"),
    LayerSpec("08_HATCH",              color=2, role="hatch"),
    LayerSpec("09_BREAK_SYMBOLS",      color=4, role="break_symbol"),
    LayerSpec("10_TABLES_ON_DRAWING",  color=8, role="tables"),
    LayerSpec("90_QA_LOW_CONFIDENCE",  color=6, role="qa"),
    LayerSpec("99_RASTER_REFERENCE",   color=9, role="raster"),
]


def by_role(role: str) -> str:
    for layer in LAYERS:
        if layer.role == role:
            return layer.name
    return "02_PART_VISIBLE"

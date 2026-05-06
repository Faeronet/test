"""Pydantic models shared across services. The canonical source of truth for
the on-disk CAD JSON format lives in `packages/schemas/cadjson.schema.json`.
The Python models below are kept in sync with that schema by hand.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Topic constants (must match Go and configs/topics.yaml) ───────────────

class Topics:
    FILE_UPLOADED = "file.uploaded"
    ARCHIVE_EXTRACTED = "archive.extracted"
    PAGE_EXTRACTED = "page.extracted"
    PAGE_PREPROCESSED = "page.preprocessed"
    PAGE_ROUTED = "page.routed"
    PAGE_DISCARDED_SPECIFICATION = "page.discarded_specification"
    PAGE_SEGMENTATION_REQUESTED = "page.segmentation.requested"
    PAGE_SEGMENTATION_DONE = "page.segmentation.done"
    PAGE_OCR_REQUESTED = "page.ocr.requested"
    PAGE_OCR_DONE = "page.ocr.done"
    PAGE_GEOMETRY_REQUESTED = "page.geometry.requested"
    PAGE_GEOMETRY_DONE = "page.geometry.done"
    PAGE_QA_REQUESTED = "page.qa.requested"
    PAGE_QA_DONE = "page.qa.done"
    PAGE_REVIEW_REQUIRED = "page.review.required"
    PAGE_REVIEW_ACCEPTED = "page.review.accepted"
    PAGE_EXPORT_REQUESTED = "page.export.requested"
    PAGE_EXPORT_DONE = "page.export.done"
    PAGE_FAILED = "page.failed"
    DEADLETTER = "deadletter"


# ─── Envelope ──────────────────────────────────────────────────────────────

class Envelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    batch_id: Optional[str] = None
    file_id: Optional[str] = None
    page_id: Optional[str] = None
    artifact_uri: Optional[str] = None
    attempt: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        return self.page_id or self.file_id or self.batch_id or self.event_id

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")


def make_envelope(event_type: str, **kwargs: Any) -> Envelope:
    return Envelope(event_type=event_type, **kwargs)


# ─── CAD JSON ──────────────────────────────────────────────────────────────

class Layer(BaseModel):
    name: str
    role: str
    color: Optional[int] = None


class Primitive(BaseModel):
    id: str
    type: str  # LINE | ARC | CIRCLE | LWPOLYLINE | TEXT
    layer: str
    confidence: Optional[float] = None
    fit: Optional[Dict[str, Any]] = None
    source_pixels: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)

    # LINE
    p1: Optional[List[float]] = None
    p2: Optional[List[float]] = None

    # CIRCLE / ARC
    center: Optional[List[float]] = None
    radius: Optional[float] = None
    start_angle_deg: Optional[float] = None
    end_angle_deg: Optional[float] = None

    # LWPOLYLINE
    vertices: Optional[List[List[float]]] = None
    closed: Optional[bool] = None

    # TEXT
    text: Optional[str] = None
    position: Optional[List[float]] = None
    height: Optional[float] = None
    rotation_deg: Optional[float] = None


class OCRBlock(BaseModel):
    id: str
    text: str
    bbox_px: List[float]  # [x1,y1,x2,y2]
    rotation_deg: Optional[float] = 0.0
    confidence: Optional[float] = None
    kind: str = "unknown"
    parsed: Optional[Dict[str, Any]] = None


class Dimension(BaseModel):
    id: str
    kind: str  # linear|diameter|radius|thread|chamfer|tolerance|unknown
    value: Optional[float] = None
    unit: Optional[str] = "mm"
    tolerance: Optional[str] = None
    anchor_px: Optional[List[float]] = None
    raw_text: Optional[str] = None


class Constraint(BaseModel):
    kind: str
    primitives: List[str]


class QASummary(BaseModel):
    requires_review: bool = False
    warnings: List[str] = Field(default_factory=list)
    raster_iou: Optional[float] = None
    chamfer_px: Optional[float] = None
    hausdorff_px: Optional[float] = None


class CADDocument(BaseModel):
    schema_version: str = "0.1"
    document: Dict[str, Any]
    layers: List[Layer]
    primitives: List[Primitive] = Field(default_factory=list)
    ocr: List[OCRBlock] = Field(default_factory=list)
    dimensions: List[Dimension] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    qa: QASummary = Field(default_factory=QASummary)


# ─── Default layers (mirrors configs/local.yaml dxf.layers) ────────────────

DEFAULT_LAYERS: List[Layer] = [
    Layer(name="00_FRAME",             role="frame",          color=8),
    Layer(name="01_TITLE_BLOCK",       role="titleblock",     color=8),
    Layer(name="02_PART_VISIBLE",      role="geometry",       color=7),
    Layer(name="03_PART_HIDDEN",       role="hidden",         color=5),
    Layer(name="04_CENTER_AXIS",       role="centerline",     color=1),
    Layer(name="05_DIM_LINES",         role="dimension",      color=3),
    Layer(name="06_DIM_TEXT",          role="dimension_text", color=3),
    Layer(name="07_TEXT_NOTES",        role="text",           color=7),
    Layer(name="08_HATCH",             role="hatch",          color=2),
    Layer(name="09_BREAK_SYMBOLS",     role="break_symbol",   color=4),
    Layer(name="10_TABLES_ON_DRAWING", role="tables",         color=8),
    Layer(name="90_QA_LOW_CONFIDENCE", role="qa",             color=6),
    Layer(name="99_RASTER_REFERENCE",  role="raster",         color=9),
]

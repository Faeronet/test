"""Compose the final CAD JSON document.

This is the orchestration layer that ties together skeleton, graph, line/
circle fitting, snapping and break-symbol handling. It accepts an optional
mask bundle (visible_geometry/centerline/etc.) and an optional list of OCR
blocks; if either is missing, the corresponding stage is skipped gracefully.

The output is a dict in the schema declared by
``packages/schemas/cadjson.schema.json`` and validated by Pydantic models
from ``drawing2dxf_common.schemas``.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from drawing2dxf_common.schemas import (
    CADDocument,
    DEFAULT_LAYERS,
    Dimension,
    OCRBlock,
    Primitive,
    QASummary,
)
from PIL import Image

from .arc_fit import ArcFit, CircleFit
from .break_symbols import enforce_collinear_around_break
from .circle_fit import detect_circle_or_arc
from .graph import extract_chains
from .line_fit import LineSegment, fit_polyline_to_chain, merge_collinear
from .skeleton import skeletonise
from .snapping import snap_angles, snap_endpoints


# ── tunables ───────────────────────────────────────────────────────────────

LINE_RESIDUAL_PX = 1.5
CIRCLE_RESIDUAL_PX = 2.0
CIRCLE_MIN_INLIERS = 30


def build_cad_json(
    *,
    visible_mask: bytes,
    page_id: str,
    batch_id: Optional[str] = None,
    file_id: Optional[str] = None,
    page_type: str = "detail_drawing",
    centerline_mask: Optional[bytes] = None,
    dimension_mask: Optional[bytes] = None,
    break_mask: Optional[bytes] = None,
    text_mask: Optional[bytes] = None,
    frame_mask: Optional[bytes] = None,
    ocr_blocks: Optional[List[Dict[str, Any]]] = None,
    image_size: Optional[tuple[int, int]] = None,
    dpi: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the full geometry pipeline and return a CAD JSON dict."""
    visible = _decode(visible_mask)
    if visible is None:
        raise ValueError("could not decode visible_geometry mask")

    h, w = visible.shape[:2]
    image_size = image_size or (w, h)

    # Subtract frame, text and break masks from visible to reduce noise.
    work = visible.copy()
    if frame_mask is not None:
        fm = _decode(frame_mask)
        if fm is not None and fm.shape == work.shape:
            work = cv2.bitwise_and(work, cv2.bitwise_not(fm))
    if text_mask is not None:
        tm = _decode(text_mask)
        if tm is not None and tm.shape == work.shape:
            work = cv2.bitwise_and(work, cv2.bitwise_not(tm))
    if break_mask is not None:
        bm = _decode(break_mask)
        if bm is not None and bm.shape == work.shape:
            work = cv2.bitwise_and(work, cv2.bitwise_not(bm))

    # Skeletonise and extract chains.
    skel = skeletonise(work)
    chains = extract_chains(skel)

    # Fit primitives.
    line_segments: List[LineSegment] = []
    circles: List[CircleFit] = []
    arcs: List[ArcFit] = []
    for chain in chains:
        # Try a circle first. If a chain forms a near-closed shape with low
        # residual, prefer the circle/arc representation.
        circle_or_arc = detect_circle_or_arc(
            chain,
            residual_tol=CIRCLE_RESIDUAL_PX,
            min_inliers=CIRCLE_MIN_INLIERS,
        )
        if isinstance(circle_or_arc, CircleFit):
            circles.append(circle_or_arc)
            continue
        if isinstance(circle_or_arc, ArcFit):
            arcs.append(circle_or_arc)
            continue
        line_segments.extend(fit_polyline_to_chain(chain, residual_tol=LINE_RESIDUAL_PX))

    line_segments = merge_collinear(line_segments)
    line_segments = snap_angles(line_segments)
    line_segments = snap_endpoints(line_segments)

    # Break-symbol handling.
    break_centers = _component_centroids(break_mask)
    if break_centers:
        line_segments = enforce_collinear_around_break(line_segments, break_centers)

    # Centerline → dedicated layer.
    center_segments: List[LineSegment] = []
    if centerline_mask is not None:
        cm = _decode(centerline_mask)
        if cm is not None:
            center_chains = extract_chains(skeletonise(cm))
            for c in center_chains:
                center_segments.extend(fit_polyline_to_chain(c, residual_tol=LINE_RESIDUAL_PX))
            center_segments = snap_angles(merge_collinear(center_segments))

    # Build CAD JSON model.
    primitives: List[Primitive] = []
    primitives.extend(_lines_to_primitives(line_segments, layer="02_PART_VISIBLE"))
    primitives.extend(_lines_to_primitives(center_segments, layer="04_CENTER_AXIS"))
    primitives.extend(_circles_to_primitives(circles))
    primitives.extend(_arcs_to_primitives(arcs))

    # Add break symbols as polyline annotations on their own layer.
    primitives.extend(_break_symbols_to_primitives(break_mask))

    ocrs: List[OCRBlock] = []
    dims: List[Dimension] = []
    for blk in (ocr_blocks or []):
        ocrs.append(OCRBlock(**{k: blk.get(k) for k in OCRBlock.model_fields.keys() if k in blk}))
        parsed = blk.get("parsed") or {}
        if parsed.get("kind") and parsed["kind"] != "unknown":
            dims.append(
                Dimension(
                    id=str(uuid.uuid4())[:8],
                    kind=parsed["kind"],
                    value=parsed.get("value"),
                    unit=parsed.get("unit") or "mm",
                    tolerance=parsed.get("tolerance"),
                    anchor_px=blk.get("bbox_px") and blk["bbox_px"][:2],
                    raw_text=blk.get("text"),
                )
            )

    qa = QASummary(
        requires_review=_requires_review(primitives),
        warnings=_collect_warnings(primitives),
    )

    px_per_mm = None
    if dpi:
        px_per_mm = dpi / 25.4

    doc = CADDocument(
        document={
            "batch_id": batch_id,
            "file_id": file_id,
            "page_id": page_id,
            "units": "mm",
            "dpi": dpi,
            "px_per_mm": px_per_mm,
            "page_type": page_type,
            "image_size_px": list(image_size),
        },
        layers=list(DEFAULT_LAYERS),
        primitives=primitives,
        ocr=ocrs,
        dimensions=dims,
        constraints=[],
        qa=qa,
    )
    return doc.model_dump(mode="json")


# ── primitive emitters ────────────────────────────────────────────────────


def _lines_to_primitives(segments: List[LineSegment], *, layer: str) -> List[Primitive]:
    out: List[Primitive] = []
    for s in segments:
        if s.length() < 1.5:
            continue
        out.append(
            Primitive(
                id=f"ln_{uuid.uuid4().hex[:8]}",
                type="LINE",
                layer=layer,
                p1=[s.p1[0], s.p1[1]],
                p2=[s.p2[0], s.p2[1]],
                confidence=_confidence_from_rms(s.rms_px),
                fit={"method": "ransac_tls", "rms_px": float(s.rms_px), "inliers": int(s.inliers)},
                source_pixels=int(s.inliers),
            )
        )
    return out


def _circles_to_primitives(circles: List[CircleFit]) -> List[Primitive]:
    out: List[Primitive] = []
    for c in circles:
        if c.r < 1.0:
            continue
        out.append(
            Primitive(
                id=f"ci_{uuid.uuid4().hex[:8]}",
                type="CIRCLE",
                layer="02_PART_VISIBLE",
                center=[c.cx, c.cy],
                radius=c.r,
                confidence=_confidence_from_rms(c.rms_px),
                fit={"method": "kasa_ls", "rms_px": float(c.rms_px), "inliers": int(c.inliers)},
                source_pixels=int(c.inliers),
            )
        )
    return out


def _arcs_to_primitives(arcs: List[ArcFit]) -> List[Primitive]:
    out: List[Primitive] = []
    for a in arcs:
        if a.r < 1.0:
            continue
        out.append(
            Primitive(
                id=f"ar_{uuid.uuid4().hex[:8]}",
                type="ARC",
                layer="02_PART_VISIBLE",
                center=[a.cx, a.cy],
                radius=a.r,
                start_angle_deg=a.start_angle_deg,
                end_angle_deg=a.end_angle_deg,
                confidence=_confidence_from_rms(a.rms_px),
                fit={"method": "kasa_ls_arc", "rms_px": float(a.rms_px), "inliers": int(a.inliers)},
                source_pixels=int(a.inliers),
            )
        )
    return out


def _break_symbols_to_primitives(break_mask: Optional[bytes]) -> List[Primitive]:
    if break_mask is None:
        return []
    bm = _decode(break_mask)
    if bm is None:
        return []
    contours, _ = cv2.findContours(bm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out: List[Primitive] = []
    for c in contours:
        if len(c) < 4:
            continue
        verts = [[float(p[0][0]), float(p[0][1])] for p in c]
        out.append(
            Primitive(
                id=f"bk_{uuid.uuid4().hex[:8]}",
                type="LWPOLYLINE",
                layer="09_BREAK_SYMBOLS",
                vertices=verts,
                closed=True,
                confidence=0.4,
                fit={"method": "contour", "rms_px": None, "inliers": len(verts)},
                source_pixels=int(cv2.contourArea(c)),
            )
        )
    return out


# ── helpers ───────────────────────────────────────────────────────────────


def _decode(buf: Optional[bytes]) -> Optional[np.ndarray]:
    if not buf:
        return None
    arr = np.frombuffer(buf, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is not None:
        return img
    try:
        with Image.open(io.BytesIO(buf)) as pil:
            pil.load()
            return np.asarray(pil.convert("L"))
    except Exception:  # noqa: BLE001
        return None


def _component_centroids(mask: Optional[bytes]) -> List[tuple[float, float]]:
    img = _decode(mask) if mask else None
    if img is None:
        return []
    num, _, _, centroids = cv2.connectedComponentsWithStats(img, connectivity=8)
    return [(float(c[0]), float(c[1])) for c in centroids[1:num]]


def _confidence_from_rms(rms: float | None) -> float:
    if rms is None or rms <= 0:
        return 0.85
    return float(np.clip(1.0 - rms / 6.0, 0.05, 0.99))


def _requires_review(primitives: List[Primitive]) -> bool:
    if not primitives:
        return True
    low_conf = sum(1 for p in primitives if (p.confidence or 1.0) < 0.55)
    return low_conf > max(5, int(0.1 * len(primitives)))


def _collect_warnings(primitives: List[Primitive]) -> List[str]:
    warnings: List[str] = []
    if not primitives:
        warnings.append("no_primitives_detected")
    if sum(1 for p in primitives if p.type == "LINE") == 0:
        warnings.append("no_line_primitives")
    return warnings

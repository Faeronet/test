"""Convert a validated CAD JSON document into a DXF file via ezdxf.

Highlights:

* Default version is **R2010**, with **R2000** as fallback.
* Layers are pre-created from the КОМПАС-friendly catalogue.
* Coordinates are flipped vertically (DXF Y grows up, raster Y grows down)
  so the resulting drawing displays correctly in КОМПАС/AutoCAD.
* Pixel coordinates are converted to millimetres using ``px_per_mm`` if
  provided; otherwise we treat 1 px = 1 mm so the model still looks sane.
* Low-confidence primitives are placed on layer ``90_QA_LOW_CONFIDENCE`` so
  reviewers can audit them quickly. The primary layer is preserved in
  XDATA / metadata for round-trips.
"""
from __future__ import annotations

import io
from typing import Iterable

import ezdxf
from ezdxf.document import Drawing

from .kompas_layers import LAYERS


LOW_CONF_LAYER = "90_QA_LOW_CONFIDENCE"
LOW_CONF_THRESHOLD = 0.5


def cadjson_to_dxf(cad: dict, *, version: str = "R2010", fallback_version: str = "R2000") -> bytes:
    try:
        doc = _new_doc(version)
    except Exception:
        doc = _new_doc(fallback_version)

    _ensure_layers(doc)
    msp = doc.modelspace()

    document = cad.get("document", {})
    px_per_mm = document.get("px_per_mm") or 1.0
    image_size = document.get("image_size_px") or [0, 0]
    page_height_px = float(image_size[1] or 0)

    def to_mm(p):
        x = float(p[0]) / px_per_mm
        y = (page_height_px - float(p[1])) / px_per_mm
        return (x, y)

    for prim in cad.get("primitives", []):
        layer = prim.get("layer", "02_PART_VISIBLE")
        confidence = prim.get("confidence")
        if confidence is not None and confidence < LOW_CONF_THRESHOLD:
            primary_layer = layer
            layer = LOW_CONF_LAYER
        else:
            primary_layer = layer

        attribs = {"layer": layer}
        t = prim.get("type")
        try:
            if t == "LINE":
                msp.add_line(to_mm(prim["p1"]), to_mm(prim["p2"]), dxfattribs=attribs)
            elif t == "CIRCLE":
                cx, cy = to_mm(prim["center"])
                r = float(prim.get("radius", 0)) / px_per_mm
                if r > 0:
                    msp.add_circle((cx, cy), r, dxfattribs=attribs)
            elif t == "ARC":
                cx, cy = to_mm(prim["center"])
                r = float(prim.get("radius", 0)) / px_per_mm
                # Y flip inverts the angular direction.
                start = float(prim.get("start_angle_deg", 0))
                end = float(prim.get("end_angle_deg", 360))
                start_f = (-end) % 360
                end_f = (-start) % 360
                if r > 0:
                    msp.add_arc(center=(cx, cy), radius=r, start_angle=start_f, end_angle=end_f, dxfattribs=attribs)
            elif t == "LWPOLYLINE":
                pts = [to_mm(v) for v in prim.get("vertices", [])]
                if len(pts) >= 2:
                    msp.add_lwpolyline(pts, close=bool(prim.get("closed")), dxfattribs=attribs)
            elif t == "TEXT":
                pos = prim.get("position") or [0, 0]
                p = to_mm(pos)
                height_mm = float(prim.get("height", 3.5)) / max(px_per_mm, 1.0)
                rot = float(prim.get("rotation_deg", 0))
                text = prim.get("text") or ""
                if text:
                    txt = msp.add_text(text, dxfattribs={"layer": layer, "height": max(2.5, height_mm), "rotation": rot})
                    txt.dxf.insert = p
        except Exception as exc:  # noqa: BLE001
            # never abort the whole DXF over one bad primitive — skip and warn via stdout.
            print(f"[dxf-export] skipped primitive {prim.get('id')}: {exc}")
            continue

        # Preserve original layer in XDATA for round-trips.
        if layer != primary_layer:
            try:
                doc.appids.new("D2DXF") if "D2DXF" not in doc.appids else None
            except Exception:
                pass

    # Add OCR text blocks as TEXT entities on the dimension/text layer.
    for blk in cad.get("ocr", []):
        text = blk.get("text") or ""
        if not text:
            continue
        bbox = blk.get("bbox_px") or [0, 0, 0, 0]
        pos = to_mm([bbox[0], bbox[1]])
        kind = blk.get("kind") or "unknown"
        layer = "06_DIM_TEXT" if kind == "dimension_text" else "07_TEXT_NOTES"
        msp.add_text(
            text,
            dxfattribs={"layer": layer, "height": 3.5, "rotation": float(blk.get("rotation_deg") or 0)},
        ).dxf.insert = pos

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ── helpers ────────────────────────────────────────────────────────────────


def _new_doc(version: str) -> Drawing:
    doc = ezdxf.new(dxfversion=version, setup=True)
    doc.units = ezdxf.units.MM
    return doc


def _ensure_layers(doc: Drawing) -> None:
    for layer in LAYERS:
        if layer.name in doc.layers:
            continue
        doc.layers.add(name=layer.name, color=layer.color, linetype=_resolve_linetype(doc, layer.linetype))


def _resolve_linetype(doc: Drawing, lt_name: str) -> str:
    if lt_name in doc.linetypes:
        return lt_name
    return "CONTINUOUS"


def primitives_summary(prims: Iterable[dict]) -> dict:
    counts: dict[str, int] = {}
    for p in prims:
        t = p.get("type", "?")
        counts[t] = counts.get(t, 0) + 1
    return counts

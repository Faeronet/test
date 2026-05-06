"""Render a small SVG/PNG preview of the CAD JSON for the web UI.

We do NOT use ezdxf's matplotlib backend (it pulls a heavy dep). Instead we
just rasterise the primitives directly with PIL — fast, dependency-light,
visually fine for review thumbnails.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw


def render_preview_png(cad: dict, *, max_side: int = 1200) -> bytes:
    document = cad.get("document", {})
    image_size = document.get("image_size_px") or [1200, 1600]
    w, h = int(image_size[0]), int(image_size[1])
    scale = min(1.0, max_side / max(w, h))
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))

    img = Image.new("RGB", (sw, sh), (255, 255, 255))
    drw = ImageDraw.Draw(img)

    for prim in cad.get("primitives", []):
        col = _color_for_layer(prim.get("layer", ""))
        t = prim.get("type")
        try:
            if t == "LINE":
                drw.line([_p(prim["p1"], scale), _p(prim["p2"], scale)], fill=col, width=1)
            elif t == "CIRCLE":
                cx, cy = _p(prim["center"], scale)
                r = float(prim.get("radius", 0)) * scale
                drw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=1)
            elif t == "ARC":
                cx, cy = _p(prim["center"], scale)
                r = float(prim.get("radius", 0)) * scale
                drw.arc([cx - r, cy - r, cx + r, cy + r],
                        start=float(prim.get("start_angle_deg", 0)),
                        end=float(prim.get("end_angle_deg", 360)),
                        fill=col, width=1)
            elif t == "LWPOLYLINE":
                verts = [_p(v, scale) for v in prim.get("vertices", [])]
                if len(verts) >= 2:
                    drw.line(verts, fill=col, width=1)
                    if prim.get("closed"):
                        drw.line([verts[-1], verts[0]], fill=col, width=1)
            elif t == "TEXT":
                drw.text(_p(prim.get("position") or [0, 0], scale), prim.get("text") or "", fill=col)
        except Exception:  # noqa: BLE001
            continue

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _p(p, scale: float):
    return (float(p[0]) * scale, float(p[1]) * scale)


def _color_for_layer(name: str):
    palette = {
        "02_PART_VISIBLE":      (0, 0, 0),
        "03_PART_HIDDEN":       (60, 60, 60),
        "04_CENTER_AXIS":       (200, 0, 0),
        "05_DIM_LINES":         (0, 120, 0),
        "06_DIM_TEXT":          (0, 120, 0),
        "07_TEXT_NOTES":        (40, 40, 40),
        "08_HATCH":             (200, 200, 0),
        "09_BREAK_SYMBOLS":     (200, 100, 0),
        "90_QA_LOW_CONFIDENCE": (255, 0, 200),
        "99_RASTER_REFERENCE":  (200, 200, 200),
    }
    return palette.get(name, (0, 0, 0))

from app.cadjson_to_dxf import cadjson_to_dxf, primitives_summary


def test_dxf_smoke():
    cad = {
        "schema_version": "0.1",
        "document": {
            "page_id": "x",
            "units": "mm",
            "page_type": "detail_drawing",
            "image_size_px": [1200, 800],
            "px_per_mm": 10.0,
        },
        "layers": [],
        "primitives": [
            {
                "id": "ln_1",
                "type": "LINE",
                "layer": "02_PART_VISIBLE",
                "p1": [100.0, 100.0],
                "p2": [600.0, 100.0],
                "confidence": 0.95,
            },
            {
                "id": "ci_1",
                "type": "CIRCLE",
                "layer": "02_PART_VISIBLE",
                "center": [400.0, 400.0],
                "radius": 80.0,
                "confidence": 0.9,
            },
            {
                "id": "ar_1",
                "type": "ARC",
                "layer": "02_PART_VISIBLE",
                "center": [600.0, 400.0],
                "radius": 60.0,
                "start_angle_deg": 0.0,
                "end_angle_deg": 180.0,
                "confidence": 0.6,
            },
            {
                "id": "lw_1",
                "type": "LWPOLYLINE",
                "layer": "09_BREAK_SYMBOLS",
                "vertices": [[10, 10], [20, 30], [40, 20]],
                "closed": False,
                "confidence": 0.7,
            },
        ],
        "ocr": [],
    }

    body = cadjson_to_dxf(cad, version="R2010")
    text = body.decode("utf-8")
    assert "AcDbLine" in text or "LINE" in text
    assert "CIRCLE" in text
    assert "ARC" in text
    assert "POLYLINE" in text
    summary = primitives_summary(cad["primitives"])
    assert summary["LINE"] == 1


def test_dxf_falls_back_to_r2000():
    cad = {
        "schema_version": "0.1",
        "document": {"page_id": "x", "units": "mm", "page_type": "detail_drawing", "image_size_px": [100, 100]},
        "layers": [],
        "primitives": [],
    }
    # Even with no primitives we should produce a valid DXF.
    body = cadjson_to_dxf(cad, version="bogus", fallback_version="R2000")
    assert b"SECTION" in body

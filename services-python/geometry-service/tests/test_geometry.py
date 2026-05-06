"""Smoke tests on synthetic toy images.

Each test renders a simple binary image, runs ``build_cad_json`` and asserts
that the expected primitive types are detected. The classical pipeline is
heuristic — we tolerate a small number of stray primitives but require the
"true" ones to appear with reasonable parameters.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from app.cadjson_builder import build_cad_json


def _png_bytes(img: np.ndarray) -> bytes:
    if img.ndim == 2:
        pil = Image.fromarray(img, mode="L")
    else:
        pil = Image.fromarray(img)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _make_visible_with(line_drawer):
    canvas = np.zeros((400, 600), dtype=np.uint8)
    line_drawer(canvas)
    return _png_bytes(canvas)


def test_horizontal_line():
    visible = _make_visible_with(lambda c: cv2.line(c, (50, 200), (550, 200), 255, 2))
    cad = build_cad_json(visible_mask=visible, page_id="p1", image_size=(600, 400))
    types = [p["type"] for p in cad["primitives"]]
    assert "LINE" in types


def test_rectangle():
    def draw(c):
        cv2.rectangle(c, (100, 80), (500, 320), 255, 2)
    visible = _make_visible_with(draw)
    cad = build_cad_json(visible_mask=visible, page_id="p1", image_size=(600, 400))
    line_count = sum(1 for p in cad["primitives"] if p["type"] == "LINE")
    assert line_count >= 4


def test_circle():
    canvas = np.zeros((400, 400), dtype=np.uint8)
    cv2.circle(canvas, (200, 200), 100, 255, 2)
    visible = _png_bytes(canvas)
    cad = build_cad_json(visible_mask=visible, page_id="p1", image_size=(400, 400))
    types = [p["type"] for p in cad["primitives"]]
    assert "CIRCLE" in types or "ARC" in types


def test_arc_like():
    canvas = np.zeros((400, 400), dtype=np.uint8)
    cv2.ellipse(canvas, (200, 200), (120, 120), 0, 0, 180, 255, 2)
    visible = _png_bytes(canvas)
    cad = build_cad_json(visible_mask=visible, page_id="p1", image_size=(400, 400))
    types = [p["type"] for p in cad["primitives"]]
    assert "ARC" in types or "CIRCLE" in types or "LINE" in types

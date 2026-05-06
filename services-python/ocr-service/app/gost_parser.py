"""Parse GOST-style notes commonly found in Russian engineering drawings.

This is a lightweight pre-processor that applied to the *raw* text of a
title-block / technical-requirements OCR block. Returns a structured map
suitable for storage as ``ocr_blocks.parsed``.

Recognised fragments include:

  - ГОСТ XXXX-YY references
  - Stahl/material strings:  "Сталь 45 ГОСТ 1050-88"
  - Surface finish:          "Ra 1.6", "Rz 6.3"
  - Mass:                    "0.42 kg"
"""
from __future__ import annotations

import re
from typing import Any, Dict


_GOST_RE = re.compile(r"ГОСТ\s*\d{3,5}(?:[-/]\d{2,4})?", re.IGNORECASE)
_RA_RE = re.compile(r"R[az]\s*[\d.,]+", re.IGNORECASE)
_MASS_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|кг)\b", re.IGNORECASE)
_MATERIAL_RE = re.compile(
    r"\b(?:Сталь|Чугун|Алюминий|АМг|Д16|Латунь|Бронза|Steel|Iron|Aluminum)\b\s*[А-Яа-яA-Z0-9-]*",
    re.IGNORECASE,
)


def parse_gost_block(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    out: Dict[str, Any] = {}
    gosts = _GOST_RE.findall(text)
    if gosts:
        out["gost_refs"] = list({g.strip() for g in gosts})
    rough = _RA_RE.findall(text)
    if rough:
        out["surface_finish"] = list({r.strip() for r in rough})
    mass = _MASS_RE.findall(text)
    if mass:
        out["mass"] = list({m.strip() for m in mass})
    material = _MATERIAL_RE.findall(text)
    if material:
        out["material"] = list({m.strip() for m in material})
    return out

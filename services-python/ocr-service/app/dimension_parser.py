"""Rule-based dimension parser.

Independent of any OCR backend. Given an arbitrary dimension string from the
drawing — which OCR may produce or which a reviewer may type by hand — it
returns a structured form usable by the geometry / DXF stages.

Examples handled:

  Ø40        → diameter 40 mm
  Ф40        → diameter 40 mm  (Cyrillic Ф commonly used as Ø)
  R25        → radius 25 mm
  M12        → thread M12
  M12x1.5    → thread M12, pitch 1.5
  80±0.2     → linear 80 mm, tolerance ±0.2
  10-0.1     → linear 10 mm, tolerance -0.1
  10+0.2     → linear 10 mm, tolerance +0.2
  10±0,2     → linear 10 mm, tolerance ±0.2 (comma decimal sep)
  1x45°      → chamfer 1×45°
  1×45°      → chamfer 1×45°
  H11        → tolerance class H11
  40H11      → linear 40 mm, tolerance class H11
  2 отв. Ø10 → diameter 10, count=2
  2 holes Ø10→ diameter 10, count=2

The parser is intentionally tolerant: anything it cannot recognise yields
``kind="unknown"`` with the original string preserved as ``raw``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict


# ── normalisation helpers ─────────────────────────────────────────────────

_DIAMETER_GLYPHS = "ØⵄⲞ⊘⌀Ф"     # Ф (cyrillic) is commonly mistaken for Ø

_SUPERSCRIPT_DEG = "°º˚"

_MULTIPLY_GLYPHS = "x×ХхXх"


def _normalize(text: str) -> str:
    s = text.strip().replace(",", ".")
    s = "".join("Ø" if c in _DIAMETER_GLYPHS else c for c in s)
    s = "".join("°" if c in _SUPERSCRIPT_DEG else c for c in s)
    s = "".join("x" if c in _MULTIPLY_GLYPHS else c for c in s)
    s = re.sub(r"\s+", " ", s)
    return s


# ── result type ────────────────────────────────────────────────────────────


@dataclass
class ParsedDimension:
    kind: str = "unknown"        # diameter | radius | linear | thread | chamfer | tolerance | unknown
    value: float | None = None
    unit: str | None = "mm"
    tolerance: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "value": self.value,
            "unit": self.unit,
            "tolerance": self.tolerance,
            "raw": self.raw,
        }
        if self.extra:
            d["extra"] = dict(self.extra)
        return d


# ── regex catalogue ───────────────────────────────────────────────────────

_NUMBER = r"[-+]?\d+(?:\.\d+)?"

# 2 отв. Ø10  /  2 holes Ø10  /  2 hole Ø10
_RE_COUNT_DIAMETER = re.compile(
    rf"^\s*(?P<count>\d+)\s*(?:отв(?:\.|ерсти[яей])?|holes?)\s*Ø\s*(?P<value>{_NUMBER})\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# 1x45°
_RE_CHAMFER = re.compile(
    rf"^\s*(?P<a>{_NUMBER})\s*x\s*(?P<b>{_NUMBER})\s*°\s*$",
    re.IGNORECASE,
)

# 80±0.2
_RE_PLUS_MINUS = re.compile(rf"^\s*(?P<value>{_NUMBER})\s*±\s*(?P<tol>{_NUMBER})\s*$")

# 10+0.2 / 10-0.1
_RE_SIGNED_TOL = re.compile(rf"^\s*(?P<value>{_NUMBER})\s*(?P<sign>[+-])\s*(?P<tol>{_NUMBER})\s*$")

# 40H11 / 40h7 / 40js6 / 40K6
_RE_VALUE_FIT = re.compile(rf"^\s*(?P<value>{_NUMBER})\s*(?P<fit>[A-Za-z]{{1,2}}\d{{1,2}})\s*$")

# H11 / h7 / k6 (no leading value)
_RE_FIT_ONLY = re.compile(r"^\s*(?P<fit>[A-Za-z]{1,2}\d{1,2})\s*$")

# Ø40H11 / Ø40 ±0.2 / Ø40
_RE_DIAMETER = re.compile(rf"^\s*Ø\s*(?P<value>{_NUMBER})(?P<rest>.*)$")

# R25 / R 25
_RE_RADIUS = re.compile(rf"^\s*R\s*(?P<value>{_NUMBER})\s*(?P<rest>.*)$", re.IGNORECASE)

# M12 / M12x1.5
_RE_THREAD = re.compile(
    rf"^\s*M\s*(?P<value>{_NUMBER})(?:\s*x\s*(?P<pitch>{_NUMBER}))?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# Plain number (linear)
_RE_LINEAR = re.compile(rf"^\s*(?P<value>{_NUMBER})\s*(?P<unit>mm|мм)?\s*$", re.IGNORECASE)


# ── public API ─────────────────────────────────────────────────────────────


def parse_dimension(text: str) -> ParsedDimension:
    raw = text
    if not text:
        return ParsedDimension(raw="")
    s = _normalize(text)

    # Count + diameter (must come before plain diameter since it includes it).
    m = _RE_COUNT_DIAMETER.match(s)
    if m:
        rest = (m.group("rest") or "").strip()
        return ParsedDimension(
            kind="diameter",
            value=float(m.group("value")),
            tolerance=_extract_tolerance(rest),
            extra={"count": int(m.group("count"))},
            raw=raw,
        )

    m = _RE_CHAMFER.match(s)
    if m:
        return ParsedDimension(
            kind="chamfer",
            value=float(m.group("a")),
            extra={"angle_deg": float(m.group("b"))},
            unit="mm",
            raw=raw,
        )

    m = _RE_DIAMETER.match(s)
    if m:
        rest = (m.group("rest") or "").strip()
        return ParsedDimension(
            kind="diameter",
            value=float(m.group("value")),
            tolerance=_extract_tolerance(rest),
            raw=raw,
        )

    m = _RE_RADIUS.match(s)
    if m:
        rest = (m.group("rest") or "").strip()
        return ParsedDimension(
            kind="radius",
            value=float(m.group("value")),
            tolerance=_extract_tolerance(rest),
            raw=raw,
        )

    m = _RE_THREAD.match(s)
    if m:
        rest = (m.group("rest") or "").strip()
        extra: Dict[str, Any] = {"thread_designator": f"M{m.group('value')}"}
        if m.group("pitch"):
            extra["pitch"] = float(m.group("pitch"))
        return ParsedDimension(
            kind="thread",
            value=float(m.group("value")),
            tolerance=_extract_tolerance(rest),
            extra=extra,
            raw=raw,
        )

    m = _RE_PLUS_MINUS.match(s)
    if m:
        return ParsedDimension(
            kind="linear",
            value=float(m.group("value")),
            tolerance=f"±{m.group('tol')}",
            raw=raw,
        )

    m = _RE_SIGNED_TOL.match(s)
    if m:
        sign = m.group("sign")
        return ParsedDimension(
            kind="linear",
            value=float(m.group("value")),
            tolerance=f"{sign}{m.group('tol')}",
            raw=raw,
        )

    m = _RE_VALUE_FIT.match(s)
    if m:
        return ParsedDimension(
            kind="linear",
            value=float(m.group("value")),
            tolerance=m.group("fit"),
            raw=raw,
        )

    m = _RE_FIT_ONLY.match(s)
    if m:
        return ParsedDimension(
            kind="tolerance",
            tolerance=m.group("fit"),
            unit=None,
            raw=raw,
        )

    m = _RE_LINEAR.match(s)
    if m:
        unit_match = m.group("unit")
        unit = "mm"
        if unit_match and unit_match.lower() in ("мм", "mm"):
            unit = "mm"
        return ParsedDimension(
            kind="linear",
            value=float(m.group("value")),
            unit=unit,
            raw=raw,
        )

    return ParsedDimension(kind="unknown", unit=None, raw=raw)


def _extract_tolerance(rest: str) -> str | None:
    """Try to extract a tolerance fragment from the trailing portion of an
    expression like ``Ø40H11`` or ``R25 +0.2``.
    """
    if not rest:
        return None
    rest = rest.strip()

    # H11 / h7 etc.
    m = re.match(r"^\s*(?P<fit>[A-Za-z]{1,2}\d{1,2})\s*$", rest)
    if m:
        return m.group("fit")

    # ±0.2
    m = re.match(rf"^\s*±\s*(?P<tol>{_NUMBER})\s*$", rest)
    if m:
        return f"±{m.group('tol')}"

    # +0.2 / -0.1
    m = re.match(rf"^\s*(?P<sign>[+-])\s*(?P<tol>{_NUMBER})\s*$", rest)
    if m:
        return f"{m.group('sign')}{m.group('tol')}"

    return None

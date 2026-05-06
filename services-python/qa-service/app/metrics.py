"""High-level QA metrics aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class QAReport:
    raster_iou: float
    chamfer_px: float
    hausdorff_px: float
    primitive_count: int
    low_confidence_count: int
    requires_review: bool
    warnings: List[str]

    def to_dict(self) -> dict:
        return {
            "raster_iou": float(self.raster_iou),
            "chamfer_px": float(self.chamfer_px),
            "hausdorff_px": float(self.hausdorff_px),
            "primitive_count": int(self.primitive_count),
            "low_confidence_count": int(self.low_confidence_count),
            "requires_review": bool(self.requires_review),
            "warnings": list(self.warnings),
        }


def review_required(
    *,
    raster_iou: float,
    chamfer_px: float,
    hausdorff_px: float,
    low_confidence_count: int,
    page_type: str,
    raster_iou_warn_below: float = 0.85,
    chamfer_warn_above_px: float = 6.0,
    hausdorff_warn_above_px: float = 12.0,
    low_conf_warn_count: int = 5,
) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    review = False
    if raster_iou < raster_iou_warn_below:
        warnings.append(f"low_raster_iou:{raster_iou:.2f}")
        review = True
    if chamfer_px > chamfer_warn_above_px:
        warnings.append(f"high_chamfer:{chamfer_px:.2f}px")
        review = True
    if hausdorff_px > hausdorff_warn_above_px:
        warnings.append(f"high_hausdorff:{hausdorff_px:.2f}px")
        review = True
    if low_confidence_count >= low_conf_warn_count:
        warnings.append(f"low_confidence_primitives:{low_confidence_count}")
        review = True
    if page_type == "unknown":
        warnings.append("page_type_unknown")
        review = True
    return review, warnings

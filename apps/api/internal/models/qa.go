package models

import (
	"time"

	"github.com/google/uuid"
)

type QAMetrics struct {
	ID             uuid.UUID      `json:"id"`
	PageID         uuid.UUID      `json:"page_id"`
	ChamferPx      *float64       `json:"chamfer_px,omitempty"`
	HausdorffPx    *float64       `json:"hausdorff_px,omitempty"`
	RasterIoU      *float64       `json:"raster_iou,omitempty"`
	RequiresReview bool           `json:"requires_review"`
	Warnings       []string       `json:"warnings"`
	Metadata       map[string]any `json:"metadata,omitempty"`
	CreatedAt      time.Time      `json:"created_at"`
}

package models

import (
	"time"

	"github.com/google/uuid"
)

const (
	PageStatusCreated      = "created"
	PageStatusExtracted    = "extracted"
	PageStatusPreprocessed = "preprocessed"
	PageStatusRouted       = "routed"
	PageStatusSegmented    = "segmented"
	PageStatusOCRDone      = "ocr_done"
	PageStatusGeometryDone = "geometry_done"
	PageStatusQADone       = "qa_done"
	PageStatusReview       = "review_required"
	PageStatusReviewed     = "reviewed"
	PageStatusExported     = "exported"
	PageStatusSkipped      = "skipped"
	PageStatusFailed       = "failed"

	PageTypeDetailDrawing      = "detail_drawing"
	PageTypeAssemblyDrawing    = "assembly_drawing"
	PageTypeSpecificationSheet = "specification_sheet"
	PageTypeBadScan            = "bad_scan"
	PageTypeUnknown            = "unknown"
)

type Page struct {
	ID                 uuid.UUID      `json:"id"`
	BatchID            uuid.UUID      `json:"batch_id"`
	FileID             uuid.UUID      `json:"file_id"`
	PageIndex          int            `json:"page_index"`
	PageType           string         `json:"page_type"`
	Status             string         `json:"status"`
	WidthPx            *int           `json:"width_px,omitempty"`
	HeightPx           *int           `json:"height_px,omitempty"`
	DPI                *int           `json:"dpi,omitempty"`
	RawImageURI        string         `json:"raw_image_uri,omitempty"`
	NormalizedImageURI string         `json:"normalized_image_uri,omitempty"`
	PreviewURI         string         `json:"preview_uri,omitempty"`
	SkipReason         string         `json:"skip_reason,omitempty"`
	Confidence         *float64       `json:"confidence,omitempty"`
	Metadata           map[string]any `json:"metadata,omitempty"`
	CreatedAt          time.Time      `json:"created_at"`
	UpdatedAt          time.Time      `json:"updated_at"`
}

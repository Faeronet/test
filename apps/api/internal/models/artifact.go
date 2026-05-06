package models

import (
	"time"

	"github.com/google/uuid"
)

const (
	ArtifactKindRaw            = "raw"
	ArtifactKindNormalized     = "normalized"
	ArtifactKindBinary         = "binary"
	ArtifactKindPreview        = "preview"
	ArtifactKindMaskVisible    = "mask_visible_geometry"
	ArtifactKindMaskHidden     = "mask_hidden_geometry"
	ArtifactKindMaskCenter     = "mask_centerline"
	ArtifactKindMaskDimGraph   = "mask_dimension_graphics"
	ArtifactKindMaskText       = "mask_text"
	ArtifactKindMaskHatch      = "mask_hatch"
	ArtifactKindMaskBreak      = "mask_break_symbol"
	ArtifactKindMaskFrame      = "mask_frame_titleblock"
	ArtifactKindMaskNoise      = "mask_noise"
	ArtifactKindOCR            = "ocr_blocks"
	ArtifactKindCADJSON        = "cad_json"
	ArtifactKindDXF            = "dxf"
	ArtifactKindQAOverlay      = "qa_overlay"
	ArtifactKindQAHeatmap      = "qa_heatmap"
	ArtifactKindExportZIP      = "export_zip"
	ArtifactKindSkipped        = "skipped_specification"
)

type Artifact struct {
	ID        uuid.UUID      `json:"id"`
	BatchID   uuid.UUID      `json:"batch_id"`
	PageID    *uuid.UUID     `json:"page_id,omitempty"`
	Kind      string         `json:"kind"`
	URI       string         `json:"uri"`
	MimeType  string         `json:"mime_type"`
	Metadata  map[string]any `json:"metadata,omitempty"`
	CreatedAt time.Time      `json:"created_at"`
}

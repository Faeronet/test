package models

import (
	"time"

	"github.com/google/uuid"
)

type CADPrimitive struct {
	ID          uuid.UUID      `json:"id"`
	PageID      uuid.UUID      `json:"page_id"`
	PrimitiveID string         `json:"primitive_id"`
	Type        string         `json:"type"`
	Layer       string         `json:"layer"`
	Geometry    map[string]any `json:"geometry"`
	Confidence  *float64       `json:"confidence,omitempty"`
	Fit         map[string]any `json:"fit,omitempty"`
	CreatedAt   time.Time      `json:"created_at"`
}

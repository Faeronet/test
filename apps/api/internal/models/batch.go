// Package models contains DTOs and DB row structs shared between the HTTP
// layer and the repository.
package models

import (
	"time"

	"github.com/google/uuid"
)

const (
	BatchStatusCreated    = "created"
	BatchStatusProcessing = "processing"
	BatchStatusReady      = "ready"
	BatchStatusFailed     = "failed"
)

type Batch struct {
	ID        uuid.UUID         `json:"id"`
	Name      string            `json:"name"`
	Status    string            `json:"status"`
	CreatedBy *uuid.UUID        `json:"created_by,omitempty"`
	Metadata  map[string]any    `json:"metadata,omitempty"`
	CreatedAt time.Time         `json:"created_at"`
	UpdatedAt time.Time         `json:"updated_at"`
}

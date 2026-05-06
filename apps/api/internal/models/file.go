package models

import (
	"time"

	"github.com/google/uuid"
)

const (
	FileStatusUploaded   = "uploaded"
	FileStatusExtracting = "extracting"
	FileStatusExtracted  = "extracted"
	FileStatusFailed     = "failed"
)

type File struct {
	ID           uuid.UUID      `json:"id"`
	BatchID      uuid.UUID      `json:"batch_id"`
	OriginalName string         `json:"original_name"`
	MimeType     string         `json:"mime_type"`
	SizeBytes    int64          `json:"size_bytes"`
	StorageURI   string         `json:"storage_uri"`
	Status       string         `json:"status"`
	Error        string         `json:"error,omitempty"`
	Metadata     map[string]any `json:"metadata,omitempty"`
	CreatedAt    time.Time      `json:"created_at"`
	UpdatedAt    time.Time      `json:"updated_at"`
}

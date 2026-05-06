// Package pipeline mirrors the canonical event envelope and topic names used
// by the API. Each Go module is independent (separate go.mod) so we redeclare
// the constants here. The single source of truth remains configs/topics.yaml.
package pipeline

import (
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
)

const (
	TopicFileUploaded               = "file.uploaded"
	TopicArchiveExtracted           = "archive.extracted"
	TopicPageExtracted              = "page.extracted"
	TopicPageFailed                 = "page.failed"
	TopicPageDiscardedSpecification = "page.discarded_specification"
	TopicDeadletter                 = "deadletter"
)

type Envelope struct {
	EventID     string         `json:"event_id"`
	EventType   string         `json:"event_type"`
	BatchID     string         `json:"batch_id,omitempty"`
	FileID      string         `json:"file_id,omitempty"`
	PageID      string         `json:"page_id,omitempty"`
	ArtifactURI string         `json:"artifact_uri,omitempty"`
	Attempt     int            `json:"attempt"`
	CreatedAt   string         `json:"created_at"`
	Payload     map[string]any `json:"payload,omitempty"`
}

func NewEnvelope(eventType string) *Envelope {
	return &Envelope{
		EventID:   uuid.NewString(),
		EventType: eventType,
		Attempt:   1,
		CreatedAt: time.Now().UTC().Format(time.RFC3339Nano),
		Payload:   map[string]any{},
	}
}

func ParseEnvelope(b []byte) (*Envelope, error) {
	var e Envelope
	if err := json.Unmarshal(b, &e); err != nil {
		return nil, err
	}
	if e.EventID == "" || e.EventType == "" {
		return nil, errors.New("invalid envelope")
	}
	return &e, nil
}

func (e *Envelope) Marshal() ([]byte, error) { return json.Marshal(e) }

func (e *Envelope) Key() string {
	switch {
	case e.PageID != "":
		return e.PageID
	case e.FileID != "":
		return e.FileID
	case e.BatchID != "":
		return e.BatchID
	default:
		return e.EventID
	}
}

package kafka

import (
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
)

// Envelope is the canonical event payload. Every worker MUST round-trip the
// same shape — Go and Python implementations must agree.
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

func (e *Envelope) Validate() error {
	if e.EventID == "" {
		return errors.New("envelope: event_id is required")
	}
	if e.EventType == "" {
		return errors.New("envelope: event_type is required")
	}
	if e.CreatedAt == "" {
		return errors.New("envelope: created_at is required")
	}
	if e.Attempt < 1 {
		return errors.New("envelope: attempt must be >= 1")
	}
	return nil
}

func (e *Envelope) Marshal() ([]byte, error) {
	if err := e.Validate(); err != nil {
		return nil, err
	}
	return json.Marshal(e)
}

func ParseEnvelope(b []byte) (*Envelope, error) {
	var e Envelope
	if err := json.Unmarshal(b, &e); err != nil {
		return nil, err
	}
	if err := e.Validate(); err != nil {
		return nil, err
	}
	return &e, nil
}

// Key returns the partitioning key for the envelope. We key on page_id when
// available so that all events for a given page land on the same partition,
// preserving stage ordering. Otherwise file_id, then batch_id, then event_id.
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

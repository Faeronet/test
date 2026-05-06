// Package jobs holds long-running orchestration helpers used by the API:
// the SSE event hub that fans out Kafka events to UI clients, and a small
// in-memory scheduler used during local development.
package jobs

import (
	"sync"

	"github.com/drawing2dxf/api/internal/kafka"
)

// EventHub is a tiny pub/sub for SSE clients. The API consumer fan-outs all
// Kafka events here, optionally filtered by batch_id.
type EventHub struct {
	mu       sync.RWMutex
	subs     map[*Subscriber]struct{}
}

type Subscriber struct {
	BatchID string  // "" = all
	C       chan *kafka.Envelope
}

func NewEventHub() *EventHub {
	return &EventHub{subs: map[*Subscriber]struct{}{}}
}

func (h *EventHub) Subscribe(batchID string) *Subscriber {
	s := &Subscriber{BatchID: batchID, C: make(chan *kafka.Envelope, 256)}
	h.mu.Lock()
	h.subs[s] = struct{}{}
	h.mu.Unlock()
	return s
}

func (h *EventHub) Unsubscribe(s *Subscriber) {
	h.mu.Lock()
	delete(h.subs, s)
	h.mu.Unlock()
	close(s.C)
}

func (h *EventHub) Publish(env *kafka.Envelope) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for s := range h.subs {
		if s.BatchID != "" && env.BatchID != "" && s.BatchID != env.BatchID {
			continue
		}
		select {
		case s.C <- env:
		default:
			// slow consumer: drop the event so we never block.
		}
	}
}

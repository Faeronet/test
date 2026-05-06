package http

import (
	"encoding/json"
	"fmt"
	stdhttp "net/http"
	"time"
)

// handleEventStream serves Server-Sent Events. The browser EventSource API
// makes this trivial to consume from the React UI.
func (s *Server) handleEventStream(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	flusher, ok := w.(stdhttp.Flusher)
	if !ok {
		writeError(w, stdhttp.StatusInternalServerError, "streaming not supported", nil)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	batchID := r.URL.Query().Get("batch_id")
	sub := s.hub.Subscribe(batchID)
	defer s.hub.Unsubscribe(sub)

	// initial hello
	fmt.Fprintf(w, ": connected\n\n")
	flusher.Flush()

	keepalive := time.NewTicker(15 * time.Second)
	defer keepalive.Stop()

	for {
		select {
		case <-r.Context().Done():
			return
		case <-keepalive.C:
			fmt.Fprintf(w, ": keepalive\n\n")
			flusher.Flush()
		case env, ok := <-sub.C:
			if !ok {
				return
			}
			data, err := json.Marshal(env)
			if err != nil {
				continue
			}
			fmt.Fprintf(w, "event: %s\n", env.EventType)
			fmt.Fprintf(w, "id: %s\n", env.EventID)
			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
		}
	}
}

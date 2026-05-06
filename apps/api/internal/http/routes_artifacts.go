package http

import (
	stdhttp "net/http"
	"time"
)

func (s *Server) handleListPageArtifacts(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	arts, err := s.repo.ListArtifactsByPage(r.Context(), id)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "list failed", err)
		return
	}
	for _, a := range arts {
		if presigned, err := s.store.PresignGet(r.Context(), a.URI, 30*time.Minute); err == nil {
			if a.Metadata == nil {
				a.Metadata = map[string]any{}
			}
			a.Metadata["presigned_url"] = presigned
		}
	}
	writeJSON(w, stdhttp.StatusOK, arts)
}

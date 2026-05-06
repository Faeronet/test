package http

import (
	"encoding/json"
	"io"
	stdhttp "net/http"

	"github.com/drawing2dxf/api/internal/models"
	"github.com/google/uuid"
)

func (s *Server) handleGetPage(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	p, err := s.repo.GetPage(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	writeJSON(w, stdhttp.StatusOK, p)
}

func (s *Server) handleGetCADJSON(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	a, err := s.repo.FindArtifact(r.Context(), id, models.ArtifactKindCADJSON)
	if notFoundOrError(w, err) {
		return
	}
	rc, err := s.store.GetObject(r.Context(), a.URI)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "fetch cad json failed", err)
		return
	}
	defer rc.Close()
	body, err := io.ReadAll(rc)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "read cad json failed", err)
		return
	}
	var doc any
	if err := json.Unmarshal(body, &doc); err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "invalid cad json on storage", err)
		return
	}
	writeJSON(w, stdhttp.StatusOK, doc)
}

func (s *Server) handleGetQA(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	q, err := s.repo.LatestQA(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	writeJSON(w, stdhttp.StatusOK, q)
}

func pathUUID(r *stdhttp.Request, key string) (uuid.UUID, error) {
	v, err := mustParam(r, key)
	if err != nil {
		return uuid.Nil, err
	}
	return uuid.Parse(v)
}

package http

import (
	stdhttp "net/http"

	"github.com/drawing2dxf/api/internal/models"
	"github.com/google/uuid"
)

type batchCreateReq struct {
	Name string `json:"name"`
}

type batchDetail struct {
	*models.Batch
	Files []*models.File `json:"files,omitempty"`
	Pages []*models.Page `json:"pages,omitempty"`
}

func (s *Server) handleCreateBatch(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	var req batchCreateReq
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid body", err)
		return
	}
	if req.Name == "" {
		req.Name = "batch-" + uuid.NewString()[:8]
	}
	b, err := s.repo.CreateBatch(r.Context(), req.Name)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "cannot create batch", err)
		return
	}
	writeJSON(w, stdhttp.StatusCreated, b)
}

func (s *Server) handleListBatches(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	limit := atoiQuery(r, "limit", 50)
	offset := atoiQuery(r, "offset", 0)
	bs, err := s.repo.ListBatches(r.Context(), limit, offset)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "list failed", err)
		return
	}
	writeJSON(w, stdhttp.StatusOK, bs)
}

func (s *Server) handleGetBatch(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	idStr, _ := mustParam(r, "batchId")
	id, err := uuid.Parse(idStr)
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid batchId", err)
		return
	}
	b, err := s.repo.GetBatch(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	files, _ := s.repo.ListFilesByBatch(r.Context(), id)
	pages, _ := s.repo.ListPagesByBatch(r.Context(), id)
	writeJSON(w, stdhttp.StatusOK, batchDetail{Batch: b, Files: files, Pages: pages})
}

// ── helpers ────────────────────────────────────────────────────────────────

func atoiQuery(r *stdhttp.Request, key string, def int) int {
	v := r.URL.Query().Get(key)
	if v == "" {
		return def
	}
	var n int
	_, err := fmtSscan(v, &n)
	if err != nil {
		return def
	}
	return n
}

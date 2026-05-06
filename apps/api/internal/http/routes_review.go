package http

import (
	stdhttp "net/http"

	"github.com/drawing2dxf/api/internal/kafka"
	"github.com/drawing2dxf/api/internal/models"
)

func (s *Server) handleReviewAccept(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	if err := s.repo.UpdatePageStatus(r.Context(), id, models.PageStatusReviewed, ""); err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "cannot update page", err)
		return
	}
	env := kafka.NewEnvelope(kafka.TopicPageReviewAccepted)
	env.PageID = id.String()
	if err := s.producer.Publish(r.Context(), kafka.TopicPageReviewAccepted, env); err != nil {
		s.logger.Sugar().Warnf("kafka publish failed: %v", err)
	}
	writeJSON(w, stdhttp.StatusOK, map[string]string{"status": "accepted"})
}

type reviewEditReq struct {
	Edits []map[string]any `json:"edits"`
	Note  string           `json:"note"`
}

func (s *Server) handleReviewEdit(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	var req reviewEditReq
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid body", err)
		return
	}
	env := kafka.NewEnvelope("page.review.edited")
	env.PageID = id.String()
	env.Payload["edits"] = req.Edits
	env.Payload["note"] = req.Note
	if err := s.producer.Publish(r.Context(), "page.review.edited", env); err != nil {
		s.logger.Sugar().Warnf("kafka publish failed: %v", err)
	}
	writeJSON(w, stdhttp.StatusOK, map[string]any{"status": "queued", "edits": len(req.Edits)})
}

func (s *Server) handleReprocess(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "pageId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid pageId", err)
		return
	}
	page, err := s.repo.GetPage(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	env := kafka.NewEnvelope(kafka.TopicPageExtracted)
	env.BatchID = page.BatchID.String()
	env.FileID = page.FileID.String()
	env.PageID = page.ID.String()
	env.ArtifactURI = page.RawImageURI
	env.Payload["reprocess"] = true
	if err := s.producer.Publish(r.Context(), kafka.TopicPageExtracted, env); err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "kafka publish failed", err)
		return
	}
	writeJSON(w, stdhttp.StatusAccepted, map[string]string{"status": "queued"})
}

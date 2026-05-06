package http

import (
	stdhttp "net/http"
	"time"

	"github.com/drawing2dxf/api/internal/db"
	"github.com/drawing2dxf/api/internal/kafka"
	"github.com/google/uuid"
)

type exportReq struct {
	Format     string `json:"format"`
	DXFVersion string `json:"dxf_version"`
}

func (s *Server) handleRequestExport(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	idStr, _ := mustParam(r, "batchId")
	batchID, err := uuid.Parse(idStr)
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid batchId", err)
		return
	}
	var req exportReq
	_ = decodeJSON(r, &req)
	if req.Format == "" {
		req.Format = "zip"
	}
	if req.DXFVersion == "" {
		req.DXFVersion = s.cfg.DXFDefaultVersion
	}

	exp := &db.Export{
		BatchID: batchID,
		Format:  req.Format,
		Status:  "pending",
	}
	created, err := s.repo.CreateExport(r.Context(), exp)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "cannot create export", err)
		return
	}

	pages, _ := s.repo.ListPagesByBatch(r.Context(), batchID)
	for _, p := range pages {
		if p.PageType == "specification_sheet" {
			continue
		}
		env := kafka.NewEnvelope(kafka.TopicPageExportRequested)
		env.BatchID = batchID.String()
		env.PageID = p.ID.String()
		env.Payload["dxf_version"] = req.DXFVersion
		env.Payload["export_id"] = created.ID.String()
		if err := s.producer.Publish(r.Context(), kafka.TopicPageExportRequested, env); err != nil {
			s.logger.Sugar().Warnf("kafka publish failed: %v", err)
		}
	}
	writeJSON(w, stdhttp.StatusAccepted, created)
}

func (s *Server) handleGetExport(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "exportId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid exportId", err)
		return
	}
	x, err := s.repo.GetExport(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	writeJSON(w, stdhttp.StatusOK, x)
}

func (s *Server) handleExportDownload(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	id, err := pathUUID(r, "exportId")
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid exportId", err)
		return
	}
	x, err := s.repo.GetExport(r.Context(), id)
	if notFoundOrError(w, err) {
		return
	}
	if x.URI == "" {
		writeError(w, stdhttp.StatusConflict, "export not ready yet", nil)
		return
	}
	url, err := s.store.PresignGet(r.Context(), x.URI, 15*time.Minute)
	if err != nil {
		writeError(w, stdhttp.StatusInternalServerError, "presign failed", err)
		return
	}
	stdhttp.Redirect(w, r, url, stdhttp.StatusFound)
}

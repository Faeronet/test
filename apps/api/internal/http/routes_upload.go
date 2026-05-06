package http

import (
	"context"
	"fmt"
	"io"
	"mime/multipart"
	stdhttp "net/http"
	"path/filepath"
	"strings"

	"github.com/drawing2dxf/api/internal/kafka"
	"github.com/drawing2dxf/api/internal/models"
	"github.com/drawing2dxf/api/internal/observability"
	"github.com/drawing2dxf/api/internal/storage"
	"github.com/google/uuid"
	"go.uber.org/zap"
)

// handleUploadFiles consumes a multipart upload of one or more files. Each
// file is streamed into MinIO and a `file.uploaded` event is produced.
func (s *Server) handleUploadFiles(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	idStr, _ := mustParam(r, "batchId")
	batchID, err := uuid.Parse(idStr)
	if err != nil {
		writeError(w, stdhttp.StatusBadRequest, "invalid batchId", err)
		return
	}
	if _, err := s.repo.GetBatch(r.Context(), batchID); notFoundOrError(w, err) {
		return
	}

	r.Body = stdhttp.MaxBytesReader(w, r.Body, s.cfg.MaxUploadBytes)
	if err := r.ParseMultipartForm(64 << 20); err != nil {
		writeError(w, stdhttp.StatusRequestEntityTooLarge, "multipart parse failed", err)
		return
	}

	form := r.MultipartForm
	if form == nil {
		writeError(w, stdhttp.StatusBadRequest, "no multipart form", nil)
		return
	}
	headers := form.File["files"]
	if len(headers) == 0 {
		// fallback for single-file `file` field
		headers = form.File["file"]
	}
	if len(headers) == 0 {
		writeError(w, stdhttp.StatusBadRequest, "no files provided (field name should be `files`)", nil)
		return
	}

	out := make([]*models.File, 0, len(headers))
	for _, fh := range headers {
		f, err := s.storeUploaded(r.Context(), batchID, fh)
		if err != nil {
			s.logger.Error("upload failed",
				zap.String("name", fh.Filename),
				zap.Error(err))
			writeError(w, stdhttp.StatusInternalServerError, "upload failed", err)
			return
		}
		out = append(out, f)
	}
	writeJSON(w, stdhttp.StatusAccepted, map[string]any{"files": out})
}

func (s *Server) storeUploaded(ctx context.Context, batchID uuid.UUID, fh *multipart.FileHeader) (*models.File, error) {
	src, err := fh.Open()
	if err != nil {
		return nil, fmt.Errorf("open upload: %w", err)
	}
	defer src.Close()

	fileID := uuid.New()
	ext := strings.ToLower(filepath.Ext(fh.Filename))
	key := storage.KeyFor("raw", batchID.String(), fileID.String()+ext)
	mime := detectMime(fh, ext)

	uri, err := s.store.PutStream(ctx, key, mime, src, fh.Size)
	if err != nil {
		return nil, fmt.Errorf("put stream: %w", err)
	}
	observability.UploadsBytes.Add(float64(fh.Size))

	file := &models.File{
		BatchID:      batchID,
		OriginalName: fh.Filename,
		MimeType:     mime,
		SizeBytes:    fh.Size,
		StorageURI:   uri,
		Status:       models.FileStatusUploaded,
		Metadata:     map[string]any{"upload_filename": fh.Filename},
	}
	created, err := s.repo.CreateFile(ctx, file)
	if err != nil {
		return nil, fmt.Errorf("persist file: %w", err)
	}

	env := kafka.NewEnvelope(kafka.TopicFileUploaded)
	env.BatchID = batchID.String()
	env.FileID = created.ID.String()
	env.ArtifactURI = uri
	env.Payload["original_name"] = created.OriginalName
	env.Payload["mime_type"] = created.MimeType
	env.Payload["size_bytes"] = created.SizeBytes
	if err := s.producer.Publish(ctx, kafka.TopicFileUploaded, env); err != nil {
		s.logger.Warn("kafka publish failed; file is stored but ingestion may be delayed",
			zap.Error(err), zap.String("file_id", created.ID.String()))
	}
	return created, nil
}

func detectMime(fh *multipart.FileHeader, ext string) string {
	if ct := fh.Header.Get("Content-Type"); ct != "" && ct != "application/octet-stream" {
		return ct
	}
	switch ext {
	case ".pdf":
		return "application/pdf"
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".tif", ".tiff":
		return "image/tiff"
	case ".webp":
		return "image/webp"
	case ".zip":
		return "application/zip"
	case ".rar":
		return "application/vnd.rar"
	case ".7z":
		return "application/x-7z-compressed"
	case ".tar":
		return "application/x-tar"
	case ".gz":
		return "application/gzip"
	case ".bz2":
		return "application/x-bzip2"
	case ".xz":
		return "application/x-xz"
	}
	return "application/octet-stream"
}

// io.Discard helper kept for symmetry with other modules.
var _ io.Writer = io.Discard

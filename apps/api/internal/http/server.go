package http

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	stdhttp "net/http"
	"time"

	"github.com/drawing2dxf/api/internal/config"
	"github.com/drawing2dxf/api/internal/db"
	"github.com/drawing2dxf/api/internal/jobs"
	d2dkafka "github.com/drawing2dxf/api/internal/kafka"
	"github.com/drawing2dxf/api/internal/storage"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// Server wires together the HTTP router and all dependencies.
type Server struct {
	cfg      *config.Config
	logger   *zap.Logger
	repo     *db.Repository
	store    *storage.Client
	producer *d2dkafka.Producer
	hub      *jobs.EventHub
	router   *chi.Mux
}

func NewServer(
	cfg *config.Config,
	logger *zap.Logger,
	repo *db.Repository,
	store *storage.Client,
	producer *d2dkafka.Producer,
	hub *jobs.EventHub,
) *Server {
	s := &Server{cfg: cfg, logger: logger, repo: repo, store: store, producer: producer, hub: hub}
	s.router = s.routes()
	return s
}

func (s *Server) Handler() stdhttp.Handler { return s.router }

func (s *Server) routes() *chi.Mux {
	r := chi.NewRouter()

	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(requestLogger(s.logger))
	r.Use(middleware.Timeout(s.cfg.RequestTimeout))
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   s.cfg.CORSAllowedOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type", "Accept"},
		AllowCredentials: false,
		MaxAge:           300,
	}))

	r.Get("/healthz", func(w stdhttp.ResponseWriter, _ *stdhttp.Request) {
		writeJSON(w, stdhttp.StatusOK, map[string]string{"status": "ok"})
	})
	r.Get("/readyz", s.handleReady)
	r.Handle("/metrics", promhttp.Handler())

	r.Route("/api", func(r chi.Router) {
		r.Route("/batches", func(r chi.Router) {
			r.Post("/", s.handleCreateBatch)
			r.Get("/", s.handleListBatches)
			r.Get("/{batchId}", s.handleGetBatch)
			r.Post("/{batchId}/upload", s.handleUploadFiles)
			r.Post("/{batchId}/export", s.handleRequestExport)
		})

		r.Route("/pages", func(r chi.Router) {
			r.Get("/{pageId}", s.handleGetPage)
			r.Get("/{pageId}/artifacts", s.handleListPageArtifacts)
			r.Get("/{pageId}/cadjson", s.handleGetCADJSON)
			r.Get("/{pageId}/qa", s.handleGetQA)

			r.Post("/{pageId}/review/accept", s.handleReviewAccept)
			r.Post("/{pageId}/review/edit", s.handleReviewEdit)
			r.Post("/{pageId}/reprocess", s.handleReprocess)
		})

		r.Route("/exports", func(r chi.Router) {
			r.Get("/{exportId}", s.handleGetExport)
			r.Get("/{exportId}/download", s.handleExportDownload)
		})

		r.Get("/events/stream", s.handleEventStream)
	})

	return r
}

func (s *Server) handleReady(w stdhttp.ResponseWriter, r *stdhttp.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err := s.repo.Pool().Ping(ctx); err != nil {
		writeError(w, stdhttp.StatusServiceUnavailable, "database not ready", err)
		return
	}
	writeJSON(w, stdhttp.StatusOK, map[string]string{"status": "ready"})
}

// ── small helpers shared by handlers ──────────────────────────────────────

func writeJSON(w stdhttp.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v == nil {
		return
	}
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w stdhttp.ResponseWriter, status int, msg string, err error) {
	body := map[string]any{"error": msg}
	if err != nil {
		body["detail"] = err.Error()
	}
	writeJSON(w, status, body)
}

func decodeJSON(r *stdhttp.Request, v any) error {
	if r.Body == nil {
		return errors.New("empty body")
	}
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(v)
}

func notFoundOrError(w stdhttp.ResponseWriter, err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, db.ErrNotFound) {
		writeError(w, stdhttp.StatusNotFound, "not found", nil)
		return true
	}
	writeError(w, stdhttp.StatusInternalServerError, "internal error", err)
	return true
}

func mustParam(r *stdhttp.Request, key string) (string, error) {
	v := chi.URLParam(r, key)
	if v == "" {
		return "", fmt.Errorf("missing %s", key)
	}
	return v, nil
}

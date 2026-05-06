// Package db wraps a pgx pool and exposes higher-level repository methods
// used by the HTTP handlers and workers. It only persists metadata; binary
// artifacts live in MinIO.
package db

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/drawing2dxf/api/internal/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Repository struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*Repository, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("pgx parse config: %w", err)
	}
	cfg.MaxConns = 20
	cfg.MinConns = 2
	cfg.MaxConnLifetime = 30 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("pgx new pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("pgx ping: %w", err)
	}
	return &Repository{pool: pool}, nil
}

func (r *Repository) Close() {
	if r.pool != nil {
		r.pool.Close()
	}
}

func (r *Repository) Pool() *pgxpool.Pool { return r.pool }

// ── Batches ──────────────────────────────────────────────────────────────

func (r *Repository) CreateBatch(ctx context.Context, name string) (*models.Batch, error) {
	row := r.pool.QueryRow(ctx, `
		INSERT INTO batches (name, status)
		VALUES ($1, $2)
		RETURNING id, name, status, created_by, metadata, created_at, updated_at`,
		name, models.BatchStatusCreated,
	)
	return scanBatch(row)
}

func (r *Repository) GetBatch(ctx context.Context, id uuid.UUID) (*models.Batch, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, name, status, created_by, metadata, created_at, updated_at
		FROM batches WHERE id = $1`, id)
	b, err := scanBatch(row)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return b, err
}

func (r *Repository) ListBatches(ctx context.Context, limit, offset int) ([]*models.Batch, error) {
	if limit <= 0 || limit > 500 {
		limit = 50
	}
	rows, err := r.pool.Query(ctx, `
		SELECT id, name, status, created_by, metadata, created_at, updated_at
		FROM batches
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2`, limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]*models.Batch, 0, limit)
	for rows.Next() {
		b, err := scanBatch(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

func (r *Repository) UpdateBatchStatus(ctx context.Context, id uuid.UUID, status string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE batches SET status = $2, updated_at = now() WHERE id = $1`,
		id, status)
	return err
}

// ── Files ────────────────────────────────────────────────────────────────

func (r *Repository) CreateFile(ctx context.Context, f *models.File) (*models.File, error) {
	meta, _ := json.Marshal(f.Metadata)
	row := r.pool.QueryRow(ctx, `
		INSERT INTO files (batch_id, original_name, mime_type, size_bytes, storage_uri, status, metadata)
		VALUES ($1,$2,$3,$4,$5,$6,$7)
		RETURNING id, batch_id, original_name, mime_type, size_bytes, storage_uri, status, COALESCE(error,''), metadata, created_at, updated_at`,
		f.BatchID, f.OriginalName, f.MimeType, f.SizeBytes, f.StorageURI, f.Status, meta,
	)
	return scanFile(row)
}

func (r *Repository) ListFilesByBatch(ctx context.Context, batchID uuid.UUID) ([]*models.File, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, batch_id, original_name, mime_type, size_bytes, storage_uri, status, COALESCE(error,''), metadata, created_at, updated_at
		FROM files WHERE batch_id = $1
		ORDER BY created_at ASC`, batchID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*models.File
	for rows.Next() {
		f, err := scanFile(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, f)
	}
	return out, rows.Err()
}

// ── Pages ────────────────────────────────────────────────────────────────

func (r *Repository) CreatePage(ctx context.Context, p *models.Page) (*models.Page, error) {
	meta, _ := json.Marshal(p.Metadata)
	row := r.pool.QueryRow(ctx, `
		INSERT INTO pages (batch_id, file_id, page_index, page_type, status, width_px, height_px, dpi, raw_image_uri, metadata)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
		RETURNING id, batch_id, file_id, page_index, page_type, status, width_px, height_px, dpi,
		          COALESCE(raw_image_uri,''), COALESCE(normalized_image_uri,''), COALESCE(preview_uri,''),
		          COALESCE(skip_reason,''), confidence, metadata, created_at, updated_at`,
		p.BatchID, p.FileID, p.PageIndex, p.PageType, p.Status,
		p.WidthPx, p.HeightPx, p.DPI, p.RawImageURI, meta,
	)
	return scanPage(row)
}

func (r *Repository) GetPage(ctx context.Context, id uuid.UUID) (*models.Page, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, batch_id, file_id, page_index, page_type, status, width_px, height_px, dpi,
		       COALESCE(raw_image_uri,''), COALESCE(normalized_image_uri,''), COALESCE(preview_uri,''),
		       COALESCE(skip_reason,''), confidence, metadata, created_at, updated_at
		FROM pages WHERE id = $1`, id)
	p, err := scanPage(row)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return p, err
}

func (r *Repository) ListPagesByBatch(ctx context.Context, batchID uuid.UUID) ([]*models.Page, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, batch_id, file_id, page_index, page_type, status, width_px, height_px, dpi,
		       COALESCE(raw_image_uri,''), COALESCE(normalized_image_uri,''), COALESCE(preview_uri,''),
		       COALESCE(skip_reason,''), confidence, metadata, created_at, updated_at
		FROM pages WHERE batch_id = $1
		ORDER BY created_at ASC`, batchID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*models.Page
	for rows.Next() {
		p, err := scanPage(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *Repository) UpdatePageStatus(ctx context.Context, id uuid.UUID, status, skipReason string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE pages
		SET status = $2,
		    skip_reason = NULLIF($3,''),
		    updated_at = now()
		WHERE id = $1`, id, status, skipReason)
	return err
}

// ── Artifacts ────────────────────────────────────────────────────────────

func (r *Repository) CreateArtifact(ctx context.Context, a *models.Artifact) (*models.Artifact, error) {
	meta, _ := json.Marshal(a.Metadata)
	row := r.pool.QueryRow(ctx, `
		INSERT INTO artifacts (batch_id, page_id, kind, uri, mime_type, metadata)
		VALUES ($1,$2,$3,$4,$5,$6)
		RETURNING id, batch_id, page_id, kind, uri, mime_type, metadata, created_at`,
		a.BatchID, a.PageID, a.Kind, a.URI, a.MimeType, meta,
	)
	return scanArtifact(row)
}

func (r *Repository) ListArtifactsByPage(ctx context.Context, pageID uuid.UUID) ([]*models.Artifact, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, batch_id, page_id, kind, uri, mime_type, metadata, created_at
		FROM artifacts WHERE page_id = $1
		ORDER BY created_at ASC`, pageID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*models.Artifact
	for rows.Next() {
		a, err := scanArtifact(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// FindArtifact returns the most recent artifact of a given kind for a page.
func (r *Repository) FindArtifact(ctx context.Context, pageID uuid.UUID, kind string) (*models.Artifact, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, batch_id, page_id, kind, uri, mime_type, metadata, created_at
		FROM artifacts WHERE page_id = $1 AND kind = $2
		ORDER BY created_at DESC LIMIT 1`, pageID, kind)
	a, err := scanArtifact(row)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return a, err
}

// ── QA ───────────────────────────────────────────────────────────────────

func (r *Repository) UpsertQAMetrics(ctx context.Context, q *models.QAMetrics) error {
	warnings, _ := json.Marshal(q.Warnings)
	meta, _ := json.Marshal(q.Metadata)
	_, err := r.pool.Exec(ctx, `
		INSERT INTO qa_metrics (page_id, chamfer_px, hausdorff_px, raster_iou, requires_review, warnings, metadata)
		VALUES ($1,$2,$3,$4,$5,$6,$7)`,
		q.PageID, q.ChamferPx, q.HausdorffPx, q.RasterIoU, q.RequiresReview, warnings, meta,
	)
	return err
}

func (r *Repository) LatestQA(ctx context.Context, pageID uuid.UUID) (*models.QAMetrics, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, page_id, chamfer_px, hausdorff_px, raster_iou, requires_review, warnings, metadata, created_at
		FROM qa_metrics WHERE page_id = $1 ORDER BY created_at DESC LIMIT 1`, pageID)
	var q models.QAMetrics
	var warnings, meta []byte
	if err := row.Scan(&q.ID, &q.PageID, &q.ChamferPx, &q.HausdorffPx, &q.RasterIoU,
		&q.RequiresReview, &warnings, &meta, &q.CreatedAt); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	_ = json.Unmarshal(warnings, &q.Warnings)
	_ = json.Unmarshal(meta, &q.Metadata)
	return &q, nil
}

// ── Exports ──────────────────────────────────────────────────────────────

type Export struct {
	ID        uuid.UUID  `json:"id"`
	BatchID   uuid.UUID  `json:"batch_id"`
	PageID    *uuid.UUID `json:"page_id,omitempty"`
	Format    string     `json:"format"`
	URI       string     `json:"uri,omitempty"`
	Status    string     `json:"status"`
	Error     string     `json:"error,omitempty"`
	CreatedAt time.Time  `json:"created_at"`
}

func (r *Repository) CreateExport(ctx context.Context, e *Export) (*Export, error) {
	row := r.pool.QueryRow(ctx, `
		INSERT INTO exports (batch_id, page_id, format, uri, status)
		VALUES ($1,$2,$3,$4,$5)
		RETURNING id, batch_id, page_id, format, COALESCE(uri,''), status, COALESCE(error,''), created_at`,
		e.BatchID, e.PageID, e.Format, nullString(e.URI), e.Status)
	var x Export
	if err := row.Scan(&x.ID, &x.BatchID, &x.PageID, &x.Format, &x.URI, &x.Status, &x.Error, &x.CreatedAt); err != nil {
		return nil, err
	}
	return &x, nil
}

func (r *Repository) GetExport(ctx context.Context, id uuid.UUID) (*Export, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, batch_id, page_id, format, COALESCE(uri,''), status, COALESCE(error,''), created_at
		FROM exports WHERE id = $1`, id)
	var x Export
	if err := row.Scan(&x.ID, &x.BatchID, &x.PageID, &x.Format, &x.URI, &x.Status, &x.Error, &x.CreatedAt); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return &x, nil
}

// ── helpers ──────────────────────────────────────────────────────────────

var ErrNotFound = errors.New("not found")

func nullString(s string) any {
	if s == "" {
		return nil
	}
	return s
}

type scanner interface {
	Scan(...any) error
}

func scanBatch(s scanner) (*models.Batch, error) {
	var b models.Batch
	var meta []byte
	if err := s.Scan(&b.ID, &b.Name, &b.Status, &b.CreatedBy, &meta, &b.CreatedAt, &b.UpdatedAt); err != nil {
		return nil, err
	}
	_ = json.Unmarshal(meta, &b.Metadata)
	return &b, nil
}

func scanFile(s scanner) (*models.File, error) {
	var f models.File
	var meta []byte
	if err := s.Scan(&f.ID, &f.BatchID, &f.OriginalName, &f.MimeType, &f.SizeBytes,
		&f.StorageURI, &f.Status, &f.Error, &meta, &f.CreatedAt, &f.UpdatedAt); err != nil {
		return nil, err
	}
	_ = json.Unmarshal(meta, &f.Metadata)
	return &f, nil
}

func scanPage(s scanner) (*models.Page, error) {
	var p models.Page
	var meta []byte
	if err := s.Scan(&p.ID, &p.BatchID, &p.FileID, &p.PageIndex, &p.PageType, &p.Status,
		&p.WidthPx, &p.HeightPx, &p.DPI,
		&p.RawImageURI, &p.NormalizedImageURI, &p.PreviewURI,
		&p.SkipReason, &p.Confidence, &meta, &p.CreatedAt, &p.UpdatedAt); err != nil {
		return nil, err
	}
	_ = json.Unmarshal(meta, &p.Metadata)
	return &p, nil
}

func scanArtifact(s scanner) (*models.Artifact, error) {
	var a models.Artifact
	var meta []byte
	if err := s.Scan(&a.ID, &a.BatchID, &a.PageID, &a.Kind, &a.URI, &a.MimeType, &meta, &a.CreatedAt); err != nil {
		return nil, err
	}
	_ = json.Unmarshal(meta, &a.Metadata)
	return &a, nil
}

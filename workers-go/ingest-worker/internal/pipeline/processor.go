package pipeline

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"
	"time"

	"github.com/drawing2dxf/ingest-worker/internal/archive"
	"github.com/drawing2dxf/ingest-worker/internal/images"
	"github.com/drawing2dxf/ingest-worker/internal/pdf"
	"github.com/drawing2dxf/ingest-worker/internal/security"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/minio/minio-go/v7"
	"go.uber.org/zap"
)

// Processor is the heart of the ingest worker. It receives `file.uploaded`
// envelopes, downloads the file from MinIO, classifies it, extracts pages,
// uploads page rasters back to MinIO, creates `pages` rows in PostgreSQL,
// and emits `page.extracted` events.
type Processor struct {
	Logger     *zap.Logger
	DB         *pgxpool.Pool
	S3         *minio.Client
	Bucket     string
	Limits     security.Limits
	Producer   Producer
	WorkRoot   string
}

// Producer is the minimal interface used by the processor to emit events.
type Producer interface {
	Publish(ctx context.Context, topic string, env *Envelope) error
}

func (p *Processor) Handle(ctx context.Context, env *Envelope) error {
	if env.FileID == "" || env.ArtifactURI == "" {
		return errors.New("ingest: missing file_id or artifact_uri")
	}
	tmp, err := os.MkdirTemp(p.WorkRoot, "ingest-"+env.FileID+"-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)

	src, err := p.download(ctx, env.ArtifactURI, tmp)
	if err != nil {
		return fmt.Errorf("download: %w", err)
	}

	originalName := stringPayload(env.Payload, "original_name")
	if originalName == "" {
		originalName = filepath.Base(src)
	}

	// Read header bytes for sniffing without loading the entire file.
	head, err := readHeader(src, 512)
	if err != nil {
		return fmt.Errorf("read header: %w", err)
	}
	kind, archFmt := security.Detect(head, originalName)
	p.Logger.Info("ingest classified",
		zap.String("file_id", env.FileID),
		zap.String("kind", kind.String()),
		zap.String("name", originalName),
	)

	switch kind {
	case security.KindImage:
		return p.handleImage(ctx, env, src, originalName)
	case security.KindPDF:
		return p.handlePDF(ctx, env, src, originalName, tmp)
	case security.KindArchive:
		return p.handleArchive(ctx, env, src, originalName, archFmt, tmp, 1)
	default:
		// mark file as failed
		_ = p.markFileStatus(ctx, env.FileID, "failed", "unrecognised file type")
		return fmt.Errorf("unsupported file kind: %s", originalName)
	}
}

// ── handlers ───────────────────────────────────────────────────────────────

func (p *Processor) handleImage(ctx context.Context, env *Envelope, src, name string) error {
	dec, err := images.NormaliseToPNG(src)
	if err != nil {
		return err
	}
	pageID := uuid.NewString()
	key := path.Join("pages", env.BatchID, env.FileID, pageID, "raw.png")
	uri, err := p.uploadBytes(ctx, key, "image/png", dec.PNG)
	if err != nil {
		return err
	}

	if err := p.insertPage(ctx, env.BatchID, env.FileID, pageID, 0, uri, dec.Width, dec.Height); err != nil {
		return err
	}
	_ = p.markFileStatus(ctx, env.FileID, "extracted", "")

	out := NewEnvelope(TopicPageExtracted)
	out.BatchID = env.BatchID
	out.FileID = env.FileID
	out.PageID = pageID
	out.ArtifactURI = uri
	out.Payload["page_index"] = 0
	out.Payload["original_name"] = name
	out.Payload["width_px"] = dec.Width
	out.Payload["height_px"] = dec.Height
	return p.Producer.Publish(ctx, TopicPageExtracted, out)
}

func (p *Processor) handlePDF(ctx context.Context, env *Envelope, src, name, work string) error {
	rdr := pdf.New(300)
	pages, err := rdr.Render(ctx, src, work)
	if err != nil {
		_ = p.markFileStatus(ctx, env.FileID, "failed", err.Error())
		return err
	}
	if len(pages) == 0 {
		_ = p.markFileStatus(ctx, env.FileID, "failed", "pdf produced no pages")
		return errors.New("pdf produced no pages")
	}

	for _, pg := range pages {
		body, err := os.ReadFile(pg.Path)
		if err != nil {
			return err
		}
		pageID := uuid.NewString()
		key := path.Join("pages", env.BatchID, env.FileID, pageID, "raw.png")
		uri, err := p.uploadBytes(ctx, key, "image/png", body)
		if err != nil {
			return err
		}
		if err := p.insertPage(ctx, env.BatchID, env.FileID, pageID, pg.Index, uri, 0, 0); err != nil {
			return err
		}
		out := NewEnvelope(TopicPageExtracted)
		out.BatchID = env.BatchID
		out.FileID = env.FileID
		out.PageID = pageID
		out.ArtifactURI = uri
		out.Payload["page_index"] = pg.Index
		out.Payload["original_name"] = name
		out.Payload["dpi"] = 300
		if err := p.Producer.Publish(ctx, TopicPageExtracted, out); err != nil {
			return err
		}
	}
	_ = p.markFileStatus(ctx, env.FileID, "extracted", "")
	return nil
}

func (p *Processor) handleArchive(ctx context.Context, env *Envelope, src, name string, fmtKind security.ArchiveFormat, work string, depth int) error {
	if depth > p.Limits.MaxArchiveDepth {
		_ = p.markFileStatus(ctx, env.FileID, "failed", security.ErrDepthLimit.Error())
		return security.ErrDepthLimit
	}
	dest := filepath.Join(work, fmt.Sprintf("ext-%d-%s", depth, uuid.NewString()[:8]))
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return err
	}

	count := 0
	total := int64(0)
	var (
		entries []archive.ExtractedFile
		err     error
	)
	switch fmtKind {
	case security.ArchiveZip:
		entries, err = archive.ExtractZip(src, dest, p.Limits, &count, &total)
	case security.ArchiveTar:
		entries, err = archive.ExtractTar(src, dest, p.Limits, &count, &total)
	case security.ArchiveTarGz:
		entries, err = archive.ExtractTarGz(src, dest, p.Limits, &count, &total)
	case security.ArchiveTarBz2:
		entries, err = archive.ExtractTarBz2(src, dest, p.Limits, &count, &total)
	case security.ArchiveTarXz:
		entries, err = archive.ExtractTarXz(src, dest, p.Limits, &count, &total)
	case security.ArchiveSevenZip:
		entries, err = archive.Extract7z(ctx, src, dest, p.Limits, &count, &total)
	case security.ArchiveRAR:
		entries, err = archive.ExtractRAR(ctx, src, dest, p.Limits, &count, &total)
	default:
		err = fmt.Errorf("unknown archive format")
	}
	if err != nil {
		_ = p.markFileStatus(ctx, env.FileID, "failed", err.Error())
		return err
	}
	p.Logger.Info("archive extracted", zap.String("file_id", env.FileID), zap.Int("entries", len(entries)))

	// Recurse over each entry — image, pdf, or nested archive.
	for _, e := range entries {
		head, err := readHeader(e.FullPath, 512)
		if err != nil {
			continue
		}
		k, af := security.Detect(head, e.RelPath)

		// Synthesize a child envelope: the original file_id stays the same (this
		// is a single user upload), but each child gets a new logical file in DB.
		childFileID := uuid.NewString()
		childKey := path.Join("raw_extracted", env.BatchID, env.FileID, childFileID+filepath.Ext(e.RelPath))
		body, rerr := os.ReadFile(e.FullPath)
		if rerr != nil {
			continue
		}
		childURI, uerr := p.uploadBytes(ctx, childKey, "application/octet-stream", body)
		if uerr != nil {
			continue
		}
		// Insert a `files` row for the child so pages can reference it.
		if err := p.insertChildFile(ctx, env.BatchID, childFileID, e.RelPath, e.Size, childURI); err != nil {
			p.Logger.Warn("insertChildFile failed", zap.Error(err))
			continue
		}

		childEnv := NewEnvelope(TopicArchiveExtracted)
		childEnv.BatchID = env.BatchID
		childEnv.FileID = childFileID
		childEnv.ArtifactURI = childURI
		childEnv.Payload["original_name"] = e.RelPath
		childEnv.Payload["parent_file_id"] = env.FileID
		_ = p.Producer.Publish(ctx, TopicArchiveExtracted, childEnv)

		switch k {
		case security.KindImage:
			_ = p.handleImage(ctx, childEnv, e.FullPath, e.RelPath)
		case security.KindPDF:
			_ = p.handlePDF(ctx, childEnv, e.FullPath, e.RelPath, work)
		case security.KindArchive:
			_ = p.handleArchive(ctx, childEnv, e.FullPath, e.RelPath, af, work, depth+1)
		default:
			p.Logger.Warn("skipping unknown nested file", zap.String("name", e.RelPath))
		}
	}
	_ = p.markFileStatus(ctx, env.FileID, "extracted", "")
	return nil
}

// ── helpers ────────────────────────────────────────────────────────────────

func (p *Processor) download(ctx context.Context, uri, dir string) (string, error) {
	key, err := keyFromURI(uri, p.Bucket)
	if err != nil {
		return "", err
	}
	obj, err := p.S3.GetObject(ctx, p.Bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return "", err
	}
	defer obj.Close()
	dst := filepath.Join(dir, "src"+filepath.Ext(key))
	f, err := os.Create(dst)
	if err != nil {
		return "", err
	}
	defer f.Close()
	if _, err := io.Copy(f, obj); err != nil {
		return "", err
	}
	return dst, nil
}

func (p *Processor) uploadBytes(ctx context.Context, key, ct string, data []byte) (string, error) {
	_, err := p.S3.PutObject(ctx, p.Bucket, key, bytes.NewReader(data), int64(len(data)), minio.PutObjectOptions{ContentType: ct})
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("s3://%s/%s", p.Bucket, key), nil
}

func (p *Processor) insertPage(ctx context.Context, batchID, fileID, pageID string, idx int, uri string, w, h int) error {
	cctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	wPtr := nullableInt(w)
	hPtr := nullableInt(h)
	_, err := p.DB.Exec(cctx, `
		INSERT INTO pages (id, batch_id, file_id, page_index, page_type, status, raw_image_uri, width_px, height_px)
		VALUES ($1,$2,$3,$4,'unknown','extracted',$5,$6,$7)`,
		pageID, batchID, fileID, idx, uri, wPtr, hPtr)
	return err
}

func (p *Processor) insertChildFile(ctx context.Context, batchID, fileID, name string, size int64, uri string) error {
	cctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	_, err := p.DB.Exec(cctx, `
		INSERT INTO files (id, batch_id, original_name, mime_type, size_bytes, storage_uri, status, metadata)
		VALUES ($1,$2,$3,'application/octet-stream',$4,$5,'extracted',$6)
		ON CONFLICT DO NOTHING`,
		fileID, batchID, name, size, uri, mustJSON(map[string]any{"source": "archive"}))
	return err
}

func (p *Processor) markFileStatus(ctx context.Context, fileID, status, errMsg string) error {
	cctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	_, err := p.DB.Exec(cctx, `
		UPDATE files
		SET status = $2, error = NULLIF($3,''), updated_at = now()
		WHERE id = $1`, fileID, status, errMsg)
	return err
}

func keyFromURI(uri, bucket string) (string, error) {
	if strings.HasPrefix(uri, "s3://") {
		u, err := url.Parse(uri)
		if err != nil {
			return "", err
		}
		if u.Host != bucket {
			return "", fmt.Errorf("uri bucket=%s mismatch %s", u.Host, bucket)
		}
		return strings.TrimPrefix(u.Path, "/"), nil
	}
	return uri, nil
}

func readHeader(p string, n int) ([]byte, error) {
	f, err := os.Open(p)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	buf := make([]byte, n)
	r, err := f.Read(buf)
	if err != nil && !errors.Is(err, io.EOF) {
		return nil, err
	}
	return buf[:r], nil
}

func stringPayload(p map[string]any, k string) string {
	if p == nil {
		return ""
	}
	if v, ok := p[k].(string); ok {
		return v
	}
	return ""
}

func nullableInt(v int) any {
	if v <= 0 {
		return nil
	}
	return v
}

func mustJSON(v any) []byte {
	b, _ := json.Marshal(v)
	return b
}

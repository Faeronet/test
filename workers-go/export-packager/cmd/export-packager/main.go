// drawing2dxf export-packager.
//
// Listens for `page.export.done` events. When all pages of a batch have
// produced DXF artifacts, packages them into a single ZIP and updates the
// `exports` row.
//
// This worker is intentionally minimal — it is a thin orchestrator over MinIO
// objects. Heavy work (DXF rendering) is done by dxf-export-service.
package main

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/twmb/franz-go/pkg/kgo"
	"go.uber.org/zap"
)

const (
	topicExportDone = "page.export.done"
)

type envelope struct {
	EventID     string         `json:"event_id"`
	EventType   string         `json:"event_type"`
	BatchID     string         `json:"batch_id"`
	PageID      string         `json:"page_id"`
	ArtifactURI string         `json:"artifact_uri"`
	Payload     map[string]any `json:"payload"`
}

func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync() //nolint:errcheck

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	pool, err := pgxpool.New(ctx, mustEnv("POSTGRES_DSN"))
	if err != nil {
		logger.Fatal("pgx", zap.Error(err))
	}
	defer pool.Close()

	mc, err := minio.New(mustEnv("MINIO_ENDPOINT"), &minio.Options{
		Creds:  credentials.NewStaticV4(mustEnv("MINIO_ACCESS_KEY"), mustEnv("MINIO_SECRET_KEY"), ""),
		Secure: false,
	})
	if err != nil {
		logger.Fatal("minio", zap.Error(err))
	}
	bucket := getenv("MINIO_BUCKET", "drawing2dxf")

	brokers := strings.Split(getenv("KAFKA_BROKERS", "redpanda:9092"), ",")
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ConsumerGroup("export-packager"),
		kgo.ConsumeTopics(topicExportDone),
		kgo.AllowAutoTopicCreation(),
	)
	if err != nil {
		logger.Fatal("kafka", zap.Error(err))
	}
	defer cl.Close()

	logger.Info("export-packager started")

	for {
		if ctx.Err() != nil {
			return
		}
		fetches := cl.PollFetches(ctx)
		fetches.EachRecord(func(r *kgo.Record) {
			var env envelope
			if err := json.Unmarshal(r.Value, &env); err != nil {
				return
			}
			if env.BatchID == "" {
				return
			}
			if err := tryPackageBatch(ctx, logger, pool, mc, bucket, env.BatchID); err != nil {
				logger.Warn("package failed", zap.Error(err))
			}
		})
	}
}

func tryPackageBatch(ctx context.Context, logger *zap.Logger, pool *pgxpool.Pool, mc *minio.Client, bucket, batchID string) error {
	rows, err := pool.Query(ctx, `
		SELECT a.uri, p.page_index, COALESCE(f.original_name, '') AS name
		FROM artifacts a
		LEFT JOIN pages p ON p.id = a.page_id
		LEFT JOIN files f ON f.id = p.file_id
		WHERE a.batch_id = $1 AND a.kind = 'dxf'
		ORDER BY p.page_index ASC`, batchID)
	if err != nil {
		return err
	}
	defer rows.Close()

	type item struct{ uri, name string; idx int }
	var items []item
	for rows.Next() {
		var (
			uri  string
			idx  *int
			name string
		)
		if err := rows.Scan(&uri, &idx, &name); err != nil {
			return err
		}
		i := 0
		if idx != nil {
			i = *idx
		}
		items = append(items, item{uri: uri, name: name, idx: i})
	}
	if len(items) == 0 {
		return errors.New("no dxf artifacts yet")
	}

	var zbuf bytes.Buffer
	zw := zip.NewWriter(&zbuf)
	for _, it := range items {
		key := strings.TrimPrefix(strings.TrimPrefix(it.uri, "s3://"+bucket+"/"), "/")
		obj, err := mc.GetObject(ctx, bucket, key, minio.GetObjectOptions{})
		if err != nil {
			return err
		}
		w, err := zw.Create(fmt.Sprintf("page_%03d_%s.dxf", it.idx, sanitize(it.name)))
		if err != nil {
			obj.Close()
			return err
		}
		if _, err := io.Copy(w, obj); err != nil {
			obj.Close()
			return err
		}
		obj.Close()
	}
	if err := zw.Close(); err != nil {
		return err
	}

	key := fmt.Sprintf("exports/%s/batch.zip", batchID)
	_, err = mc.PutObject(ctx, bucket, key, bytes.NewReader(zbuf.Bytes()), int64(zbuf.Len()), minio.PutObjectOptions{
		ContentType: "application/zip",
	})
	if err != nil {
		return err
	}
	uri := fmt.Sprintf("s3://%s/%s", bucket, key)

	_, err = pool.Exec(ctx, `
		UPDATE exports SET uri = $2, status = 'ready', updated_at = now()
		WHERE batch_id = $1 AND status <> 'ready'`, batchID, uri)
	if err != nil {
		return err
	}
	logger.Info("export packaged",
		zap.String("batch_id", batchID),
		zap.Int("pages", len(items)),
		zap.String("uri", uri),
		zap.Time("at", time.Now()),
	)
	return nil
}

func sanitize(s string) string {
	s = strings.ReplaceAll(s, "/", "_")
	s = strings.ReplaceAll(s, "\\", "_")
	if s == "" {
		return "page"
	}
	return s
}

func mustEnv(k string) string {
	v := os.Getenv(k)
	if v == "" {
		panic("env " + k + " required")
	}
	return v
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

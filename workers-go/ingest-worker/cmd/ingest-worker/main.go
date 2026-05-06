// drawing2dxf ingest-worker.
//
// Subscribes to `file.uploaded`, downloads each upload from MinIO, classifies
// it (image / PDF / archive), recursively extracts archives with hard safety
// limits, splits PDFs into pages, normalises images to PNG, persists `pages`
// rows in PostgreSQL and emits `page.extracted` events to Kafka so that the
// preprocess service can pick them up.
package main

import (
	"context"
	"errors"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"

	"github.com/drawing2dxf/ingest-worker/internal/pipeline"
	"github.com/drawing2dxf/ingest-worker/internal/security"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/twmb/franz-go/pkg/kgo"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

func main() {
	if err := run(); err != nil {
		println("ingest-worker fatal:", err.Error())
		os.Exit(1)
	}
}

func run() error {
	logger, _ := zap.Config{
		Level:    zap.NewAtomicLevelAt(zap.InfoLevel),
		Encoding: "json",
		EncoderConfig: zapcore.EncoderConfig{
			TimeKey:        "ts",
			LevelKey:       "level",
			MessageKey:     "msg",
			EncodeTime:     zapcore.ISO8601TimeEncoder,
			EncodeLevel:    zapcore.LowercaseLevelEncoder,
			EncodeDuration: zapcore.SecondsDurationEncoder,
		},
		OutputPaths:      []string{"stdout"},
		ErrorOutputPaths: []string{"stderr"},
	}.Build()
	defer logger.Sync() //nolint:errcheck

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	dsn := mustEnv("POSTGRES_DSN")
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return err
	}
	defer pool.Close()

	mc, err := minio.New(mustEnv("MINIO_ENDPOINT"), &minio.Options{
		Creds:  credentials.NewStaticV4(mustEnv("MINIO_ACCESS_KEY"), mustEnv("MINIO_SECRET_KEY"), ""),
		Secure: envBool("MINIO_USE_SSL", false),
		Region: getEnv("MINIO_REGION", "us-east-1"),
	})
	if err != nil {
		return err
	}
	bucket := getEnv("MINIO_BUCKET", "drawing2dxf")

	brokers := strings.Split(getEnv("KAFKA_BROKERS", "redpanda:9092"), ",")
	clientID := getEnv("KAFKA_CLIENT_ID", "ingest-worker")
	group := getEnv("KAFKA_CONSUMER_GROUP", "ingest-worker")

	prod, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ClientID(clientID+"-prod"),
		kgo.AllowAutoTopicCreation(),
	)
	if err != nil {
		return err
	}
	defer prod.Close()

	cons, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ClientID(clientID),
		kgo.ConsumerGroup(group),
		kgo.ConsumeTopics(pipeline.TopicFileUploaded),
		kgo.AllowAutoTopicCreation(),
		kgo.DisableAutoCommit(),
	)
	if err != nil {
		return err
	}
	defer cons.Close()

	limits := security.DefaultLimits()
	limits.MaxArchiveFiles = envInt("MAX_ARCHIVE_FILES", limits.MaxArchiveFiles)
	limits.MaxArchiveDepth = envInt("MAX_ARCHIVE_DEPTH", limits.MaxArchiveDepth)
	limits.MaxArchiveUncompressedBytes = envInt64("MAX_ARCHIVE_UNCOMPRESSED_BYTES", limits.MaxArchiveUncompressedBytes)
	limits.MaxPagePixels = envInt64("MAX_PAGE_PIXELS", limits.MaxPagePixels)

	proc := &pipeline.Processor{
		Logger:   logger,
		DB:       pool,
		S3:       mc,
		Bucket:   bucket,
		Limits:   limits,
		Producer: &kafkaProducer{cl: prod, log: logger},
		WorkRoot: getEnv("INGEST_WORK_ROOT", "/tmp"),
	}

	logger.Info("ingest-worker started",
		zap.Strings("brokers", brokers),
		zap.String("bucket", bucket),
		zap.Any("limits", limits),
	)

	for {
		if err := ctx.Err(); err != nil {
			return nil
		}
		fetches := cons.PollFetches(ctx)
		if errs := fetches.Errors(); len(errs) > 0 {
			for _, e := range errs {
				if errors.Is(e.Err, context.Canceled) {
					return nil
				}
				logger.Warn("fetch err", zap.Error(e.Err))
			}
		}
		fetches.EachRecord(func(r *kgo.Record) {
			env, err := pipeline.ParseEnvelope(r.Value)
			if err != nil {
				logger.Warn("invalid envelope", zap.Error(err), zap.String("topic", r.Topic))
				return
			}
			if err := proc.Handle(ctx, env); err != nil {
				logger.Error("handle failed",
					zap.String("event_id", env.EventID),
					zap.String("file_id", env.FileID),
					zap.Error(err))
				if env.Attempt < 5 {
					return // do not commit; rebalance/retry
				}
				// dead-letter
				dl := pipeline.NewEnvelope("deadletter")
				dl.BatchID = env.BatchID
				dl.FileID = env.FileID
				dl.Payload["original_topic"] = r.Topic
				dl.Payload["error"] = err.Error()
				dl.Payload["original_event"] = env
				body, _ := dl.Marshal()
				prod.ProduceSync(ctx, &kgo.Record{
					Topic: pipeline.TopicDeadletter,
					Key:   []byte(dl.Key()),
					Value: body,
				})
			}
		})
		if err := cons.CommitUncommittedOffsets(ctx); err != nil {
			logger.Warn("commit", zap.Error(err))
		}
	}
}

// ── kafka producer adapter ────────────────────────────────────────────────

type kafkaProducer struct {
	cl  *kgo.Client
	log *zap.Logger
}

func (p *kafkaProducer) Publish(ctx context.Context, topic string, env *pipeline.Envelope) error {
	body, err := env.Marshal()
	if err != nil {
		return err
	}
	res := p.cl.ProduceSync(ctx, &kgo.Record{
		Topic: topic,
		Key:   []byte(env.Key()),
		Value: body,
	})
	return res.FirstErr()
}

// ── env helpers ────────────────────────────────────────────────────────────

func mustEnv(k string) string {
	v := os.Getenv(k)
	if v == "" {
		panic("env " + k + " required")
	}
	return v
}

func getEnv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

func envBool(k string, d bool) bool {
	if v := os.Getenv(k); v != "" {
		switch strings.ToLower(v) {
		case "1", "true", "yes":
			return true
		case "0", "false", "no":
			return false
		}
	}
	return d
}

func envInt(k string, d int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return d
}

func envInt64(k string, d int64) int64 {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			return n
		}
	}
	return d
}

// drawing2dxf API server.
//
// Wires together: chi router, pgx repository, MinIO storage client, franz-go
// Kafka producer, and a passive consumer that fan-outs every event to SSE
// subscribers. All long-running work happens in workers; the API only
// persists metadata, stores raw uploads in MinIO, and emits events.
package main

import (
	"context"
	"errors"
	stdhttp "net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/drawing2dxf/api/internal/config"
	"github.com/drawing2dxf/api/internal/db"
	httpapi "github.com/drawing2dxf/api/internal/http"
	"github.com/drawing2dxf/api/internal/jobs"
	"github.com/drawing2dxf/api/internal/kafka"
	"github.com/drawing2dxf/api/internal/observability"
	"github.com/drawing2dxf/api/internal/storage"
	"go.uber.org/zap"
)

func main() {
	if err := run(); err != nil {
		// best-effort stderr without a logger
		println("fatal:", err.Error())
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	logger, err := observability.NewLogger(cfg.LogLevel)
	if err != nil {
		return err
	}
	defer logger.Sync() //nolint:errcheck

	logger.Info("api starting", zap.String("config", cfg.String()))

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	repo, err := db.New(ctx, cfg.PostgresDSN)
	if err != nil {
		return err
	}
	defer repo.Close()

	store, err := storage.New(storage.Config{
		Endpoint:       cfg.MinIOEndpoint,
		PublicEndpoint: cfg.MinIOPublicEndpoint,
		AccessKey:      cfg.MinIOAccessKey,
		SecretKey:      cfg.MinIOSecretKey,
		Bucket:         cfg.MinIOBucket,
		UseSSL:         cfg.MinIOUseSSL,
		Region:         cfg.MinIORegion,
	})
	if err != nil {
		return err
	}
	if err := store.EnsureBucket(ctx); err != nil {
		logger.Warn("EnsureBucket failed (will retry lazily)", zap.Error(err))
	}

	producer, err := kafka.NewProducer(cfg.KafkaBrokers, cfg.KafkaClientID+"-prod", logger)
	if err != nil {
		return err
	}
	defer producer.Close()

	hub := jobs.NewEventHub()
	if err := jobs.Tap(ctx, cfg.KafkaBrokers, cfg.KafkaConsumerGroup+"-tap", cfg.KafkaClientID+"-tap", hub, logger); err != nil {
		logger.Warn("event tap not started", zap.Error(err))
	}

	srv := httpapi.NewServer(cfg, logger, repo, store, producer, hub)
	httpServer := &stdhttp.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	go func() {
		logger.Info("listening", zap.String("addr", cfg.HTTPAddr))
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, stdhttp.ErrServerClosed) {
			logger.Fatal("http server error", zap.Error(err))
		}
	}()

	<-ctx.Done()
	logger.Info("shutting down")
	shutdownCtx, sCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer sCancel()
	return httpServer.Shutdown(shutdownCtx)
}

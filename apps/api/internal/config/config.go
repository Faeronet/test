// Package config loads runtime settings from environment variables. Defaults
// match the values in .env.example. Reads of optional YAML files are not done
// here on purpose: the API is happy with env-only configuration so that
// containers stay 12-factor.
package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	HTTPAddr           string
	PublicBaseURL      string
	LogLevel           string
	CORSAllowedOrigins []string

	PostgresDSN string

	MinIOEndpoint        string
	MinIOPublicEndpoint  string
	MinIOAccessKey       string
	MinIOSecretKey       string
	MinIOBucket          string
	MinIOUseSSL          bool
	MinIORegion          string

	KafkaBrokers       []string
	KafkaClientID      string
	KafkaConsumerGroup string

	MaxUploadBytes int64
	RequestTimeout time.Duration

	DXFDefaultVersion  string
	DXFFallbackVersion string
}

func Load() (*Config, error) {
	cfg := &Config{
		HTTPAddr:           getEnv("API_HTTP_ADDR", ":8080"),
		PublicBaseURL:      getEnv("API_PUBLIC_BASE_URL", "http://localhost:8080"),
		LogLevel:           getEnv("API_LOG_LEVEL", "info"),
		CORSAllowedOrigins: splitCSV(getEnv("API_CORS_ALLOWED_ORIGINS", "http://localhost:5173")),

		PostgresDSN: getEnv("POSTGRES_DSN", ""),

		MinIOEndpoint:       getEnv("MINIO_ENDPOINT", "minio:9000"),
		MinIOPublicEndpoint: getEnv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
		MinIOAccessKey:      getEnv("MINIO_ACCESS_KEY", ""),
		MinIOSecretKey:      getEnv("MINIO_SECRET_KEY", ""),
		MinIOBucket:         getEnv("MINIO_BUCKET", "drawing2dxf"),
		MinIOUseSSL:         getEnvBool("MINIO_USE_SSL", false),
		MinIORegion:         getEnv("MINIO_REGION", "us-east-1"),

		KafkaBrokers:       splitCSV(getEnv("KAFKA_BROKERS", "redpanda:9092")),
		KafkaClientID:      getEnv("KAFKA_CLIENT_ID", "drawing2dxf-api"),
		KafkaConsumerGroup: getEnv("KAFKA_CONSUMER_GROUP", "drawing2dxf-api"),

		MaxUploadBytes: getEnvInt64("MAX_UPLOAD_BYTES", 2<<30),
		RequestTimeout: time.Duration(getEnvInt("API_REQUEST_TIMEOUT_SEC", 60)) * time.Second,

		DXFDefaultVersion:  getEnv("DXF_DEFAULT_VERSION", "R2010"),
		DXFFallbackVersion: getEnv("DXF_FALLBACK_VERSION", "R2000"),
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (c *Config) Validate() error {
	if c.PostgresDSN == "" {
		return errors.New("POSTGRES_DSN is required")
	}
	if c.MinIOAccessKey == "" || c.MinIOSecretKey == "" {
		return errors.New("MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required")
	}
	if len(c.KafkaBrokers) == 0 {
		return errors.New("KAFKA_BROKERS is required")
	}
	return nil
}

func (c *Config) String() string {
	return fmt.Sprintf("Config{addr=%s public=%s bucket=%s brokers=%v}",
		c.HTTPAddr, c.PublicBaseURL, c.MinIOBucket, c.KafkaBrokers)
}

// ── helpers ────────────────────────────────────────────────────────────────

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func getEnvInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func getEnvInt64(key string, def int64) int64 {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			return n
		}
	}
	return def
}

func getEnvBool(key string, def bool) bool {
	if v := os.Getenv(key); v != "" {
		switch strings.ToLower(v) {
		case "1", "true", "yes", "y", "on":
			return true
		case "0", "false", "no", "n", "off":
			return false
		}
	}
	return def
}

func splitCSV(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

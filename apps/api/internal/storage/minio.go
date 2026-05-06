// Package storage wraps MinIO/S3 operations used by the API. Binary artifacts
// (raw uploads, normalized images, masks, CAD JSON, DXF, previews) are
// addressed by `s3://<bucket>/<key>` URIs. Database stores only URIs.
package storage

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/url"
	"path"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type Config struct {
	Endpoint        string
	PublicEndpoint  string
	AccessKey       string
	SecretKey       string
	Bucket          string
	UseSSL          bool
	Region          string
}

type Client struct {
	cfg Config
	mc  *minio.Client
}

func New(cfg Config) (*Client, error) {
	mc, err := minio.New(cfg.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
		Region: cfg.Region,
	})
	if err != nil {
		return nil, fmt.Errorf("minio: %w", err)
	}
	return &Client{cfg: cfg, mc: mc}, nil
}

// EnsureBucket creates the configured bucket if it does not exist.
func (c *Client) EnsureBucket(ctx context.Context) error {
	exists, err := c.mc.BucketExists(ctx, c.cfg.Bucket)
	if err != nil {
		return fmt.Errorf("BucketExists: %w", err)
	}
	if !exists {
		if err := c.mc.MakeBucket(ctx, c.cfg.Bucket, minio.MakeBucketOptions{Region: c.cfg.Region}); err != nil {
			return fmt.Errorf("MakeBucket: %w", err)
		}
	}
	return nil
}

func (c *Client) Bucket() string { return c.cfg.Bucket }

// PutStream uploads a stream of unknown size and returns the S3 URI.
func (c *Client) PutStream(ctx context.Context, key, contentType string, r io.Reader, size int64) (string, error) {
	_, err := c.mc.PutObject(ctx, c.cfg.Bucket, key, r, size, minio.PutObjectOptions{
		ContentType: contentType,
	})
	if err != nil {
		return "", fmt.Errorf("PutObject %s: %w", key, err)
	}
	return c.URI(key), nil
}

// PutBytes is a small helper for known-size payloads (CAD JSON, manifests).
func (c *Client) PutBytes(ctx context.Context, key, contentType string, data []byte) (string, error) {
	return c.PutStream(ctx, key, contentType, bytesReader(data), int64(len(data)))
}

// GetObject returns a streaming reader for the given URI or key.
func (c *Client) GetObject(ctx context.Context, uriOrKey string) (io.ReadCloser, error) {
	key, err := c.parseKey(uriOrKey)
	if err != nil {
		return nil, err
	}
	obj, err := c.mc.GetObject(ctx, c.cfg.Bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, err
	}
	return obj, nil
}

// PresignGet returns a temporary download URL.
func (c *Client) PresignGet(ctx context.Context, uriOrKey string, ttl time.Duration) (string, error) {
	key, err := c.parseKey(uriOrKey)
	if err != nil {
		return "", err
	}
	u, err := c.mc.PresignedGetObject(ctx, c.cfg.Bucket, key, ttl, url.Values{})
	if err != nil {
		return "", err
	}
	if c.cfg.PublicEndpoint != "" {
		u = rewriteHost(u, c.cfg.PublicEndpoint)
	}
	return u.String(), nil
}

// URI returns the canonical s3:// URI for a key.
func (c *Client) URI(key string) string {
	return fmt.Sprintf("s3://%s/%s", c.cfg.Bucket, strings.TrimPrefix(key, "/"))
}

// KeyFor returns a deterministic object key under a logical prefix tree.
func KeyFor(parts ...string) string {
	for i, p := range parts {
		parts[i] = strings.Trim(p, "/")
	}
	return path.Join(parts...)
}

// ── helpers ────────────────────────────────────────────────────────────────

func (c *Client) parseKey(uriOrKey string) (string, error) {
	if strings.HasPrefix(uriOrKey, "s3://") {
		u, err := url.Parse(uriOrKey)
		if err != nil {
			return "", err
		}
		if u.Host != c.cfg.Bucket {
			return "", fmt.Errorf("uri bucket=%s does not match configured bucket=%s", u.Host, c.cfg.Bucket)
		}
		return strings.TrimPrefix(u.Path, "/"), nil
	}
	if uriOrKey == "" {
		return "", errors.New("empty uri/key")
	}
	return strings.TrimPrefix(uriOrKey, "/"), nil
}

func rewriteHost(u *url.URL, publicEndpoint string) *url.URL {
	pu, err := url.Parse(publicEndpoint)
	if err != nil {
		return u
	}
	out := *u
	out.Scheme = pu.Scheme
	out.Host = pu.Host
	return &out
}

func bytesReader(b []byte) io.Reader { return bytes.NewReader(b) }

// Package security centralises the safety policies used by the ingest worker
// when handling untrusted user uploads.
//
// These limits are intentionally conservative defaults; they can be tuned via
// environment variables (see Config in cmd/ingest-worker/main.go).
package security

import (
	"errors"
	"path/filepath"
	"strings"
)

type Limits struct {
	MaxArchiveFiles            int   // total entries allowed inside one archive (recursively)
	MaxArchiveDepth            int   // nested archive depth
	MaxArchiveUncompressedBytes int64 // sum of decompressed bytes
	MaxPagePixels              int64 // width*height ceiling for a single image page
}

func DefaultLimits() Limits {
	return Limits{
		MaxArchiveFiles:             10_000,
		MaxArchiveDepth:             8,
		MaxArchiveUncompressedBytes: 20 << 30,
		MaxPagePixels:               200_000_000,
	}
}

var (
	ErrPathTraversal   = errors.New("archive entry escapes destination")
	ErrAbsolutePath    = errors.New("archive entry has absolute path")
	ErrSymlinkDenied   = errors.New("archive entry is a symlink (denied)")
	ErrFileLimit       = errors.New("archive contains too many files")
	ErrSizeLimit       = errors.New("archive exceeds uncompressed size limit")
	ErrDepthLimit      = errors.New("nested archive depth exceeded")
	ErrPagePixelsLimit = errors.New("image page exceeds max-pixels limit")
)

// SafeJoin verifies that `name` (an entry inside an archive) cannot escape
// the destination directory and is not absolute. It returns the cleaned
// joined path or an error.
func SafeJoin(dest, name string) (string, error) {
	if name == "" {
		return "", errors.New("empty archive entry name")
	}
	// Reject absolute paths and Windows drives.
	if strings.HasPrefix(name, "/") || strings.HasPrefix(name, "\\") {
		return "", ErrAbsolutePath
	}
	if len(name) >= 2 && name[1] == ':' {
		return "", ErrAbsolutePath
	}
	cleaned := filepath.Clean(name)
	if strings.HasPrefix(cleaned, "..") || strings.Contains(cleaned, string(filepath.Separator)+"..") {
		return "", ErrPathTraversal
	}

	full := filepath.Join(dest, cleaned)
	rel, err := filepath.Rel(dest, full)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", ErrPathTraversal
	}
	return full, nil
}

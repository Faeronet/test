// Package archive implements safe extractors for ZIP/TAR/TAR.GZ/TAR.BZ2/
// TAR.XZ/7Z/RAR. Each extractor enforces the security limits from the
// security package: file count, depth, uncompressed size, no symlinks, no
// absolute paths, no path traversal.
package archive

import (
	"archive/zip"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/drawing2dxf/ingest-worker/internal/security"
)

// ExtractedFile is a small handle returned for each successfully extracted
// regular file.
type ExtractedFile struct {
	RelPath  string
	FullPath string
	Size     int64
}

// ExtractZip extracts the zip archive at `src` into `dest`. The destination
// directory is created if needed.
func ExtractZip(src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return nil, err
	}
	zr, err := zip.OpenReader(src)
	if err != nil {
		return nil, fmt.Errorf("zip open: %w", err)
	}
	defer zr.Close()

	out := make([]ExtractedFile, 0, len(zr.File))
	for _, f := range zr.File {
		if *count >= lim.MaxArchiveFiles {
			return nil, security.ErrFileLimit
		}
		*count++

		mode := f.Mode()
		if mode&os.ModeSymlink != 0 {
			return nil, security.ErrSymlinkDenied
		}
		fp, err := security.SafeJoin(dest, f.Name)
		if err != nil {
			return nil, err
		}

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(fp, 0o755); err != nil {
				return nil, err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(fp), 0o755); err != nil {
			return nil, err
		}
		written, err := writeWithLimit(zr, f, fp, lim, total)
		if err != nil {
			return nil, err
		}
		rel, _ := filepath.Rel(dest, fp)
		out = append(out, ExtractedFile{RelPath: rel, FullPath: fp, Size: written})
	}
	return out, nil
}

func writeWithLimit(zr *zip.ReadCloser, f *zip.File, fp string, lim security.Limits, total *int64) (int64, error) {
	rc, err := f.Open()
	if err != nil {
		return 0, err
	}
	defer rc.Close()
	return copyToFileWithLimit(rc, fp, lim, total)
}

func copyToFileWithLimit(r io.Reader, fp string, lim security.Limits, total *int64) (int64, error) {
	dst, err := os.OpenFile(fp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return 0, err
	}
	defer dst.Close()

	buf := make([]byte, 64*1024)
	var written int64
	for {
		n, rerr := r.Read(buf)
		if n > 0 {
			*total += int64(n)
			if *total > lim.MaxArchiveUncompressedBytes {
				return written, security.ErrSizeLimit
			}
			if _, werr := dst.Write(buf[:n]); werr != nil {
				return written, werr
			}
			written += int64(n)
		}
		if errors.Is(rerr, io.EOF) {
			break
		}
		if rerr != nil {
			return written, rerr
		}
	}
	return written, nil
}

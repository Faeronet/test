package archive

import (
	"archive/tar"
	"compress/bzip2"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/drawing2dxf/ingest-worker/internal/security"
	"github.com/ulikunitz/xz"
)

func ExtractTar(src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	f, err := os.Open(src)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return extractTarStream(f, dest, lim, count, total)
}

func ExtractTarGz(src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	f, err := os.Open(src)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return nil, fmt.Errorf("gzip: %w", err)
	}
	defer gz.Close()
	return extractTarStream(gz, dest, lim, count, total)
}

func ExtractTarBz2(src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	f, err := os.Open(src)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return extractTarStream(bzip2.NewReader(f), dest, lim, count, total)
}

func ExtractTarXz(src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	f, err := os.Open(src)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	xr, err := xz.NewReader(f)
	if err != nil {
		return nil, fmt.Errorf("xz: %w", err)
	}
	return extractTarStream(xr, dest, lim, count, total)
}

func extractTarStream(r io.Reader, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return nil, err
	}
	tr := tar.NewReader(r)
	out := make([]ExtractedFile, 0, 16)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("tar next: %w", err)
		}
		if *count >= lim.MaxArchiveFiles {
			return nil, security.ErrFileLimit
		}
		*count++

		switch hdr.Typeflag {
		case tar.TypeSymlink, tar.TypeLink:
			return nil, security.ErrSymlinkDenied
		}

		fp, err := security.SafeJoin(dest, hdr.Name)
		if err != nil {
			return nil, err
		}
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(fp, 0o755); err != nil {
				return nil, err
			}
		case tar.TypeReg, tar.TypeRegA:
			if err := os.MkdirAll(filepath.Dir(fp), 0o755); err != nil {
				return nil, err
			}
			n, err := copyToFileWithLimit(tr, fp, lim, total)
			if err != nil {
				return nil, err
			}
			rel, _ := filepath.Rel(dest, fp)
			out = append(out, ExtractedFile{RelPath: rel, FullPath: fp, Size: n})
		}
	}
	return out, nil
}

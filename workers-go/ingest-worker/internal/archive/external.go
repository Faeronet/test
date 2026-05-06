package archive

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/drawing2dxf/ingest-worker/internal/security"
)

// Extract7z runs `7zz` (or `7z`) inside a controlled subprocess and validates
// every extracted path stays within `dest`. The user-uploaded archive is read
// only; the binary cannot escape the sandbox temp dir.
func Extract7z(ctx context.Context, src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	bin := pickBinary("7zz", "7z")
	if bin == "" {
		return nil, errors.New("7z binary (7zz/7z) not found in PATH")
	}
	return runArchiveTool(ctx, bin, []string{"x", "-y", "-bd", "-bb0", "-snl", "-snh", "-o" + dest, "--", src}, dest, lim, count, total)
}

// ExtractRAR delegates to `unar` which is safer than the proprietary unrar.
func ExtractRAR(ctx context.Context, src, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	bin := pickBinary("unar")
	if bin == "" {
		return nil, errors.New("unar binary not found in PATH")
	}
	return runArchiveTool(ctx, bin, []string{"-no-directory", "-no-quarantine", "-force-overwrite", "-o", dest, src}, dest, lim, count, total)
}

func pickBinary(names ...string) string {
	for _, n := range names {
		if p, err := exec.LookPath(n); err == nil {
			return p
		}
	}
	return ""
}

func runArchiveTool(ctx context.Context, bin string, args []string, dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return nil, err
	}
	cctx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(cctx, bin, args...)
	cmd.Stdout = os.Stderr // pipe both to stderr so docker logs capture them
	cmd.Stderr = os.Stderr
	cmd.Env = []string{"PATH=" + os.Getenv("PATH"), "HOME=/tmp", "LANG=C.UTF-8"}
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("%s failed: %w", bin, err)
	}
	return walkAndValidate(dest, lim, count, total)
}

// walkAndValidate enumerates files under `dest`, rejecting symlinks and
// enforcing per-archive limits. Returns the list of regular files.
func walkAndValidate(dest string, lim security.Limits, count *int, total *int64) ([]ExtractedFile, error) {
	out := make([]ExtractedFile, 0, 16)
	err := filepath.WalkDir(dest, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return security.ErrSymlinkDenied
		}
		// Validate path containment.
		if !strings.HasPrefix(filepath.Clean(path)+string(filepath.Separator), filepath.Clean(dest)+string(filepath.Separator)) {
			return security.ErrPathTraversal
		}
		*count++
		if *count > lim.MaxArchiveFiles {
			return security.ErrFileLimit
		}
		*total += info.Size()
		if *total > lim.MaxArchiveUncompressedBytes {
			return security.ErrSizeLimit
		}
		rel, _ := filepath.Rel(dest, path)
		out = append(out, ExtractedFile{RelPath: rel, FullPath: path, Size: info.Size()})
		return nil
	})
	if err != nil {
		return nil, err
	}
	return out, nil
}

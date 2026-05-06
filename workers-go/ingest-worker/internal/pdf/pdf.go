// Package pdf renders pages out of PDF documents using poppler's `pdftoppm`.
// We never trust the input PDF — pdftoppm is sandboxed by Docker and runs
// with a context timeout.
package pdf

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type Page struct {
	Index int    // zero-based
	Path  string // absolute path to PNG
}

type Renderer struct {
	DPI     int
	Timeout time.Duration
}

func New(dpi int) *Renderer {
	if dpi <= 0 {
		dpi = 300
	}
	return &Renderer{DPI: dpi, Timeout: 10 * time.Minute}
}

// Render renders all pages of `src` to PNG files inside `outDir`. It returns
// a slice ordered by page index.
func (r *Renderer) Render(ctx context.Context, src, outDir string) ([]Page, error) {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return nil, err
	}
	bin, err := exec.LookPath("pdftoppm")
	if err != nil {
		return nil, fmt.Errorf("pdftoppm not found in PATH: %w", err)
	}
	cctx, cancel := context.WithTimeout(ctx, r.Timeout)
	defer cancel()

	prefix := filepath.Join(outDir, "page")
	cmd := exec.CommandContext(cctx, bin,
		"-png",
		"-r", fmt.Sprintf("%d", r.DPI),
		src, prefix,
	)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	cmd.Env = []string{"PATH=" + os.Getenv("PATH"), "HOME=/tmp", "LANG=C.UTF-8"}
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("pdftoppm failed: %w", err)
	}

	entries, err := os.ReadDir(outDir)
	if err != nil {
		return nil, err
	}
	pages := make([]Page, 0, len(entries))
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".png") {
			continue
		}
		full := filepath.Join(outDir, e.Name())
		pages = append(pages, Page{Path: full})
	}
	sort.Slice(pages, func(i, j int) bool { return pages[i].Path < pages[j].Path })
	for i := range pages {
		pages[i].Index = i
	}
	return pages, nil
}

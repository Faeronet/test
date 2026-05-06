// Package images normalises raster inputs to PNG using only Go's standard
// library codecs (PNG, JPEG, GIF). For TIFF/WEBP we fall back to copying the
// bytes; downstream Python services handle re-encoding through OpenCV/PIL.
package images

import (
	"bytes"
	"errors"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"os"
	"strings"

	_ "image/gif"
)

type Decoded struct {
	Width  int
	Height int
	PNG    []byte // re-encoded to PNG when possible
}

// NormaliseToPNG attempts to load the file and re-encode as PNG. For formats
// the standard library cannot decode (TIFF, WEBP) it returns the raw bytes
// with width/height = 0; callers can still upload them and let the Python
// preprocess service re-decode.
func NormaliseToPNG(srcPath string) (*Decoded, error) {
	raw, err := os.ReadFile(srcPath)
	if err != nil {
		return nil, err
	}
	low := strings.ToLower(srcPath)
	if strings.HasSuffix(low, ".tif") || strings.HasSuffix(low, ".tiff") || strings.HasSuffix(low, ".webp") || strings.HasSuffix(low, ".bmp") {
		return &Decoded{PNG: raw}, nil
	}

	img, _, err := image.Decode(bytes.NewReader(raw))
	if err != nil {
		// last resort: pass through bytes unchanged.
		return &Decoded{PNG: raw}, nil
	}
	b := img.Bounds()
	var buf bytes.Buffer
	enc := &png.Encoder{CompressionLevel: png.BestSpeed}
	if err := enc.Encode(&buf, img); err != nil {
		return nil, err
	}
	return &Decoded{
		Width:  b.Dx(),
		Height: b.Dy(),
		PNG:    buf.Bytes(),
	}, nil
}

// QuickJPEGToPNG re-encodes a JPEG byte slice directly into PNG bytes. Used
// when we have raw bytes already streamed from MinIO.
func QuickJPEGToPNG(jpegBytes []byte) ([]byte, error) {
	img, err := jpeg.Decode(bytes.NewReader(jpegBytes))
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// SaveToTemp writes `r` to a temp file under dir and returns its path.
func SaveToTemp(dir, name string, r io.Reader) (string, error) {
	if name == "" {
		name = "tmp.bin"
	}
	dst, err := os.CreateTemp(dir, "ingest-*-"+name)
	if err != nil {
		return "", err
	}
	defer dst.Close()
	if _, err := io.Copy(dst, r); err != nil {
		return "", err
	}
	return dst.Name(), nil
}

// ErrUnsupportedImage is returned when nothing in the toolbelt can decode a
// frame.
var ErrUnsupportedImage = errors.New("unsupported image format")

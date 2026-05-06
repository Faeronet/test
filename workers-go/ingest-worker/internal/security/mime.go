package security

import (
	"bytes"
	"net/http"
	"strings"
)

// FileKind is a coarse classification used by the ingest pipeline to pick the
// next stage. We never trust the user-provided extension on its own.
type FileKind int

const (
	KindUnknown FileKind = iota
	KindImage
	KindPDF
	KindArchive
)

func (k FileKind) String() string {
	switch k {
	case KindImage:
		return "image"
	case KindPDF:
		return "pdf"
	case KindArchive:
		return "archive"
	default:
		return "unknown"
	}
}

// ArchiveFormat further narrows archive type.
type ArchiveFormat int

const (
	ArchiveNone ArchiveFormat = iota
	ArchiveZip
	ArchiveTar
	ArchiveTarGz
	ArchiveTarBz2
	ArchiveTarXz
	ArchiveSevenZip
	ArchiveRAR
)

// Detect inspects the file header (magic bytes) and the original extension to
// classify the upload. Magic bytes win if they conflict with the extension.
func Detect(head []byte, originalName string) (FileKind, ArchiveFormat) {
	ext := strings.ToLower(extOf(originalName))

	// JPEG, PNG, TIFF, WEBP, BMP, GIF
	ct := http.DetectContentType(head)
	switch {
	case strings.HasPrefix(ct, "image/"):
		return KindImage, ArchiveNone
	case ct == "application/pdf":
		return KindPDF, ArchiveNone
	}

	// Some image formats (TIFF/WEBP older revisions) may not be detected
	// reliably by net/http; sniff manually.
	if isTIFF(head) || isWEBP(head) {
		return KindImage, ArchiveNone
	}

	if isPDF(head) {
		return KindPDF, ArchiveNone
	}

	switch {
	case isZip(head):
		return KindArchive, ArchiveZip
	case is7z(head):
		return KindArchive, ArchiveSevenZip
	case isRAR(head):
		return KindArchive, ArchiveRAR
	case isGzip(head):
		// .tar.gz vs plain .gz — ext-based hint is acceptable, fallback to TarGz
		if strings.HasSuffix(ext, ".tar.gz") || ext == ".tgz" || strings.HasSuffix(ext, ".tar") {
			return KindArchive, ArchiveTarGz
		}
		return KindArchive, ArchiveTarGz
	case isBzip2(head):
		return KindArchive, ArchiveTarBz2
	case isXZ(head):
		return KindArchive, ArchiveTarXz
	case isTar(head):
		return KindArchive, ArchiveTar
	}

	switch ext {
	case ".zip":
		return KindArchive, ArchiveZip
	case ".rar":
		return KindArchive, ArchiveRAR
	case ".7z":
		return KindArchive, ArchiveSevenZip
	case ".tar":
		return KindArchive, ArchiveTar
	case ".tar.gz", ".tgz":
		return KindArchive, ArchiveTarGz
	case ".tar.bz2", ".tbz2":
		return KindArchive, ArchiveTarBz2
	case ".tar.xz", ".txz":
		return KindArchive, ArchiveTarXz
	case ".pdf":
		return KindPDF, ArchiveNone
	case ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp":
		return KindImage, ArchiveNone
	}

	return KindUnknown, ArchiveNone
}

// ── header sniffers ────────────────────────────────────────────────────────

func isPDF(b []byte) bool   { return bytes.HasPrefix(b, []byte("%PDF-")) }
func isZip(b []byte) bool   { return bytes.HasPrefix(b, []byte{0x50, 0x4B, 0x03, 0x04}) || bytes.HasPrefix(b, []byte{0x50, 0x4B, 0x05, 0x06}) || bytes.HasPrefix(b, []byte{0x50, 0x4B, 0x07, 0x08}) }
func is7z(b []byte) bool    { return bytes.HasPrefix(b, []byte{'7', 'z', 0xBC, 0xAF, 0x27, 0x1C}) }
func isRAR(b []byte) bool   { return bytes.HasPrefix(b, []byte("Rar!\x1A\x07\x00")) || bytes.HasPrefix(b, []byte("Rar!\x1A\x07\x01\x00")) }
func isGzip(b []byte) bool  { return len(b) >= 2 && b[0] == 0x1F && b[1] == 0x8B }
func isBzip2(b []byte) bool { return bytes.HasPrefix(b, []byte("BZh")) }
func isXZ(b []byte) bool    { return bytes.HasPrefix(b, []byte{0xFD, '7', 'z', 'X', 'Z', 0x00}) }
func isTar(b []byte) bool {
	if len(b) < 265 {
		return false
	}
	return bytes.Equal(b[257:262], []byte{'u', 's', 't', 'a', 'r'})
}
func isTIFF(b []byte) bool {
	return bytes.HasPrefix(b, []byte{'I', 'I', 0x2A, 0x00}) || bytes.HasPrefix(b, []byte{'M', 'M', 0x00, 0x2A})
}
func isWEBP(b []byte) bool {
	return len(b) >= 12 && bytes.Equal(b[0:4], []byte("RIFF")) && bytes.Equal(b[8:12], []byte("WEBP"))
}

func extOf(name string) string {
	lower := strings.ToLower(name)
	for _, suffix := range []string{".tar.gz", ".tar.bz2", ".tar.xz"} {
		if strings.HasSuffix(lower, suffix) {
			return suffix
		}
	}
	if i := strings.LastIndex(lower, "."); i >= 0 {
		return lower[i:]
	}
	return ""
}

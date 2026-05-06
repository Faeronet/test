package security

import "testing"

func TestDetectPNG(t *testing.T) {
	header := []byte{0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0}
	k, _ := Detect(header, "scan.png")
	if k != KindImage {
		t.Fatalf("expected image, got %v", k)
	}
}

func TestDetectPDF(t *testing.T) {
	k, _ := Detect([]byte("%PDF-1.7\n"), "drawing.pdf")
	if k != KindPDF {
		t.Fatalf("expected pdf, got %v", k)
	}
}

func TestDetectZip(t *testing.T) {
	k, fmtKind := Detect([]byte{0x50, 0x4B, 0x03, 0x04, 0, 0, 0, 0}, "ar.zip")
	if k != KindArchive || fmtKind != ArchiveZip {
		t.Fatalf("expected zip, got kind=%v fmt=%v", k, fmtKind)
	}
}

func TestDetectExtensionFallback(t *testing.T) {
	k, fmtKind := Detect([]byte{0, 0, 0, 0}, "weird.7z")
	if k != KindArchive || fmtKind != ArchiveSevenZip {
		t.Fatalf("expected 7z fallback, got %v %v", k, fmtKind)
	}
}

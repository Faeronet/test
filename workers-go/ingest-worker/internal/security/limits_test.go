package security

import (
	"path/filepath"
	"testing"
)

func TestSafeJoinHappyPath(t *testing.T) {
	dest := t.TempDir()
	out, err := SafeJoin(dest, "subdir/file.txt")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := filepath.Join(dest, "subdir", "file.txt")
	if out != want {
		t.Fatalf("got %s want %s", out, want)
	}
}

func TestSafeJoinRejectsTraversal(t *testing.T) {
	dest := t.TempDir()
	cases := []string{
		"../etc/passwd",
		"sub/../../etc/passwd",
		"sub/../../../etc/passwd",
	}
	for _, c := range cases {
		t.Run(c, func(t *testing.T) {
			if _, err := SafeJoin(dest, c); err == nil {
				t.Fatalf("expected error for %s", c)
			}
		})
	}
}

func TestSafeJoinRejectsAbsolute(t *testing.T) {
	dest := t.TempDir()
	for _, c := range []string{"/etc/passwd", `\windows\system32`, `C:/foo`} {
		if _, err := SafeJoin(dest, c); err == nil {
			t.Fatalf("expected error for %s", c)
		}
	}
}

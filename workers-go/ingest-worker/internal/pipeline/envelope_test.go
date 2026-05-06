package pipeline

import "testing"

func TestEnvelopeRoundTrip(t *testing.T) {
	env := NewEnvelope("page.preprocessed")
	env.BatchID = "b"
	env.PageID = "p"
	env.Payload["foo"] = "bar"

	body, err := env.Marshal()
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	out, err := ParseEnvelope(body)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if out.EventType != env.EventType || out.PageID != "p" {
		t.Fatalf("round-trip mismatch: %+v", out)
	}
	if out.Key() != "p" {
		t.Fatalf("expected page-id key, got %q", out.Key())
	}
}

func TestEnvelopeRejectsBlank(t *testing.T) {
	if _, err := ParseEnvelope([]byte(`{}`)); err == nil {
		t.Fatal("expected error for blank envelope")
	}
}

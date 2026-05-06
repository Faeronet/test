package kafka

import "testing"

func TestEnvelopeValidate(t *testing.T) {
	e := NewEnvelope("file.uploaded")
	if err := e.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestEnvelopeRoundTrip(t *testing.T) {
	e := NewEnvelope("page.preprocessed")
	e.BatchID = "b"
	e.FileID = "f"
	e.PageID = "p"
	body, err := e.Marshal()
	if err != nil {
		t.Fatal(err)
	}
	out, err := ParseEnvelope(body)
	if err != nil {
		t.Fatal(err)
	}
	if out.PageID != "p" || out.Key() != "p" {
		t.Fatalf("got %+v", out)
	}
}

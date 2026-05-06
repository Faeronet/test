package models

// CADJSON is the canonical intermediate representation between the geometry
// service and the DXF exporter. The on-disk schema lives in
// packages/schemas/cadjson.schema.json. We do NOT re-validate it here in Go;
// validation is performed in Python services using pydantic and the JSON
// schema, while the API treats it as opaque structured payload.
type CADJSON map[string]any

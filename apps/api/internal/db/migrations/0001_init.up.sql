-- 0001_init.up.sql
-- Core schema for drawing2dxf metadata. Binary artifacts live in MinIO.

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    display_name  TEXT,
    role          TEXT NOT NULL DEFAULT 'engineer',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS batches (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'created',
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_batches_status     ON batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_created_at ON batches(created_at DESC);

CREATE TABLE IF NOT EXISTS files (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id       UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    original_name  TEXT NOT NULL,
    mime_type      TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes     BIGINT NOT NULL DEFAULT 0,
    storage_uri    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'uploaded',
    error          TEXT,
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_files_batch ON files(batch_id);

CREATE TABLE IF NOT EXISTS pages (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id             UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    file_id              UUID NOT NULL REFERENCES files(id)   ON DELETE CASCADE,
    page_index           INTEGER NOT NULL DEFAULT 0,
    page_type            TEXT NOT NULL DEFAULT 'unknown',
    status               TEXT NOT NULL DEFAULT 'created',
    width_px             INTEGER,
    height_px            INTEGER,
    dpi                  INTEGER,
    raw_image_uri        TEXT,
    normalized_image_uri TEXT,
    preview_uri          TEXT,
    skip_reason          TEXT,
    confidence           DOUBLE PRECISION,
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pages_batch  ON pages(batch_id);
CREATE INDEX IF NOT EXISTS idx_pages_file   ON pages(file_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_type   ON pages(page_type);

CREATE TABLE IF NOT EXISTS artifacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    page_id     UUID REFERENCES pages(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    uri         TEXT NOT NULL,
    mime_type   TEXT NOT NULL DEFAULT 'application/octet-stream',
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_artifacts_batch ON artifacts(batch_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_page  ON artifacts(page_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind  ON artifacts(kind);

CREATE TABLE IF NOT EXISTS jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID REFERENCES batches(id) ON DELETE CASCADE,
    page_id     UUID REFERENCES pages(id) ON DELETE CASCADE,
    stage       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    attempt     INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_page_stage ON jobs(page_id, stage)
    WHERE page_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_stage  ON jobs(stage);

CREATE TABLE IF NOT EXISTS job_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID REFERENCES jobs(id) ON DELETE CASCADE,
    batch_id    UUID,
    page_id     UUID,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_job_events_batch ON job_events(batch_id);
CREATE INDEX IF NOT EXISTS idx_job_events_page  ON job_events(page_id);

CREATE TABLE IF NOT EXISTS page_classifications (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id       UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    page_type     TEXT NOT NULL,
    confidence    DOUBLE PRECISION,
    reason        TEXT,
    model_version TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pageclass_page ON page_classifications(page_id);

CREATE TABLE IF NOT EXISTS ocr_blocks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id     UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    bbox_px     JSONB NOT NULL,
    rotation    DOUBLE PRECISION DEFAULT 0,
    confidence  DOUBLE PRECISION,
    kind        TEXT,
    parsed      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ocr_blocks_page ON ocr_blocks(page_id);

CREATE TABLE IF NOT EXISTS cad_primitives (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id      UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    primitive_id TEXT NOT NULL,
    type         TEXT NOT NULL,
    layer        TEXT NOT NULL,
    geometry     JSONB NOT NULL,
    confidence   DOUBLE PRECISION,
    fit          JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cad_prim_page ON cad_primitives(page_id);

CREATE TABLE IF NOT EXISTS cad_constraints (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id     UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    primitives  JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS qa_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    chamfer_px      DOUBLE PRECISION,
    hausdorff_px    DOUBLE PRECISION,
    raster_iou      DOUBLE PRECISION,
    requires_review BOOLEAN NOT NULL DEFAULT FALSE,
    warnings        JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_qa_metrics_page ON qa_metrics(page_id);

CREATE TABLE IF NOT EXISTS review_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id     UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id),
    status      TEXT NOT NULL DEFAULT 'open',
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_edits (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    page_id      UUID NOT NULL,
    operation    TEXT NOT NULL,
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    page_id     UUID REFERENCES pages(id) ON DELETE CASCADE,
    format      TEXT NOT NULL,
    uri         TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    error       TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_exports_batch ON exports(batch_id);

CREATE TABLE IF NOT EXISTS model_versions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role         TEXT NOT NULL,
    name         TEXT NOT NULL,
    version      TEXT NOT NULL,
    weights_uri  TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_versions_role ON model_versions(role);

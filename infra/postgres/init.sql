-- This file is loaded automatically by the postgres docker image on first
-- startup. It creates the role + database + extensions. Tables are managed by
-- golang-migrate migrations under apps/api/internal/db/migrations.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

SHELL := /bin/bash

ENV_FILE ?= .env
COMPOSE  ?= docker compose
PROJECT  ?= drawing2dxf

# default goal
.DEFAULT_GOAL := help

# ─────────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────────────────────────────────────────────────────────
# Compose lifecycle
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: up
up: ## docker compose up -d (CPU mode)
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build

.PHONY: up-gpu
up-gpu: ## docker compose up -d with GPU overrides
	$(COMPOSE) --env-file $(ENV_FILE) -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

.PHONY: down
down: ## docker compose down
	$(COMPOSE) --env-file $(ENV_FILE) down

.PHONY: down-volumes
down-volumes: ## docker compose down -v (drops volumes)
	$(COMPOSE) --env-file $(ENV_FILE) down -v

.PHONY: logs
logs: ## Tail logs of all services
	$(COMPOSE) --env-file $(ENV_FILE) logs -f --tail=200

.PHONY: ps
ps: ## docker compose ps
	$(COMPOSE) --env-file $(ENV_FILE) ps

# ─────────────────────────────────────────────────────────────────────────────
# Per-service shortcuts
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: api
api: ## Run API locally (go run)
	cd apps/api && go run ./cmd/api

.PHONY: web
web: ## Run web dev server
	cd apps/web && npm run dev

.PHONY: ingest
ingest: ## Run ingest-worker locally
	cd workers-go/ingest-worker && go run ./cmd/ingest-worker

# ─────────────────────────────────────────────────────────────────────────────
# Tests / lint / fmt
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: test
test: ## Run all tests (Go + Python)
	@echo "==> Go tests"
	cd apps/api && go test ./... || true
	cd workers-go/ingest-worker && go test ./... || true
	cd workers-go/export-packager && go test ./... || true
	@echo "==> Python tests"
	@for svc in ocr-service geometry-service dxf-export-service; do \
		echo "    -> $$svc"; \
		PYTHONPATH=services-python/common:services-python/$$svc python -m pytest services-python/$$svc/tests -q || exit 1; \
	done

.PHONY: lint
lint: ## Lint Go and Python code
	cd apps/api && go vet ./... || true
	cd workers-go/ingest-worker && go vet ./... || true
	@command -v ruff >/dev/null 2>&1 && ruff check services-python || echo "ruff not installed, skipping"

.PHONY: fmt
fmt: ## Format code
	cd apps/api && gofmt -w . || true
	cd workers-go/ingest-worker && gofmt -w . || true
	@command -v ruff >/dev/null 2>&1 && ruff format services-python || true

# ─────────────────────────────────────────────────────────────────────────────
# DB migrations
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: migrate-up
migrate-up: ## Run DB migrations (up)
	$(COMPOSE) --env-file $(ENV_FILE) run --rm migrate -path=/migrations -database=$$POSTGRES_DSN up

.PHONY: migrate-down
migrate-down: ## Rollback last migration
	$(COMPOSE) --env-file $(ENV_FILE) run --rm migrate -path=/migrations -database=$$POSTGRES_DSN down 1

# ─────────────────────────────────────────────────────────────────────────────
# Storage / seed
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: create-bucket
create-bucket: ## Create MinIO bucket(s)
	@bash scripts/create_bucket.sh

.PHONY: seed
seed: ## Seed dev data
	cd apps/api && go run ../../scripts/dev_seed.go || go run ../../scripts/dev_seed.go

.PHONY: run-sample
run-sample: ## End-to-end mock pipeline on bundled fixture
	bash scripts/run_local_pipeline.sh

# ─────────────────────────────────────────────────────────────────────────────
# Docs
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: docs-architecture
docs-architecture: ## Render docs/architecture.mmd to PNG/SVG (requires mmdc)
	@if command -v mmdc >/dev/null 2>&1; then \
		mmdc -i docs/architecture.mmd -o docs/architecture.svg && \
		mmdc -i docs/architecture.mmd -o docs/architecture.png ; \
	else \
		echo "mermaid-cli (mmdc) not found, skipping render. Install with: npm i -g @mermaid-js/mermaid-cli" ; \
	fi

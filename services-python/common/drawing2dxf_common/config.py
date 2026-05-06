"""Centralised configuration loaded from environment variables.

Each service imports `settings` and reads what it needs. Optional fields are
left as ``None`` so individual services can implement strict validation if
they care.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import BaseModel, Field


def _split_csv(value: str | None, default: List[str] | None = None) -> List[str]:
    if not value:
        return list(default or [])
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings(BaseModel):
    # ── kafka / redpanda ──────────────────────────────────────────────
    kafka_brokers: List[str] = Field(default_factory=lambda: _split_csv(os.getenv("KAFKA_BROKERS"), ["redpanda:9092"]))
    kafka_client_id: str = Field(default_factory=lambda: os.getenv("KAFKA_CLIENT_ID", "drawing2dxf-py"))
    kafka_consumer_group: str = Field(default_factory=lambda: os.getenv("KAFKA_CONSUMER_GROUP", "drawing2dxf-py"))

    # ── minio / s3 ────────────────────────────────────────────────────
    minio_endpoint: str = Field(default_factory=lambda: os.getenv("MINIO_ENDPOINT", "minio:9000"))
    minio_access_key: str = Field(default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", ""))
    minio_secret_key: str = Field(default_factory=lambda: os.getenv("MINIO_SECRET_KEY", ""))
    minio_bucket: str = Field(default_factory=lambda: os.getenv("MINIO_BUCKET", "drawing2dxf"))
    minio_use_ssl: bool = Field(default_factory=lambda: os.getenv("MINIO_USE_SSL", "false").lower() in ("1", "true", "yes"))
    minio_region: str = Field(default_factory=lambda: os.getenv("MINIO_REGION", "us-east-1"))

    # ── postgres (optional) ───────────────────────────────────────────
    postgres_dsn: str | None = Field(default_factory=lambda: os.getenv("POSTGRES_DSN"))

    # ── runtime ───────────────────────────────────────────────────────
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "info"))
    enable_gpu: bool = Field(default_factory=lambda: os.getenv("ENABLE_GPU", "false").lower() in ("1", "true", "yes"))
    service_name: str = Field(default_factory=lambda: os.getenv("SERVICE_NAME", "drawing2dxf-service"))

    # ── models (optional weights paths) ───────────────────────────────
    router_weights: str | None = Field(default_factory=lambda: os.getenv("MODEL_ROUTER_WEIGHTS"))
    segmentation_weights: str | None = Field(default_factory=lambda: os.getenv("SEGMENTATION_WEIGHTS"))
    ocr_weights_dir: str | None = Field(default_factory=lambda: os.getenv("OCR_WEIGHTS_DIR"))
    vlm_weights_dir: str | None = Field(default_factory=lambda: os.getenv("VLM_WEIGHTS_DIR"))
    sam_weights: str | None = Field(default_factory=lambda: os.getenv("SAM_WEIGHTS"))

    # implementation switches
    router_impl: str = Field(default_factory=lambda: os.getenv("ROUTER_IMPL", "rules"))
    seg_impl: str = Field(default_factory=lambda: os.getenv("SEG_IMPL", "classical"))
    ocr_impl: str = Field(default_factory=lambda: os.getenv("OCR_IMPL", "mock"))
    vlm_impl: str = Field(default_factory=lambda: os.getenv("VLM_IMPL", "mock"))
    sam_impl: str = Field(default_factory=lambda: os.getenv("SAM_IMPL", "mock"))

    # dxf
    dxf_default_version: str = Field(default_factory=lambda: os.getenv("DXF_DEFAULT_VERSION", "R2010"))
    dxf_fallback_version: str = Field(default_factory=lambda: os.getenv("DXF_FALLBACK_VERSION", "R2000"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

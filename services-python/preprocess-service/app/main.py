"""Preprocess service entry point.

Mode of operation:
* Subscribes to ``page.extracted``.
* Downloads raw page from MinIO.
* Runs preprocessing pipeline.
* Uploads ``normalized``, ``binary`` and ``preview`` artifacts back to MinIO.
* Updates the page row in PostgreSQL with normalised / preview URIs and
  quality metadata.
* Emits ``page.preprocessed`` and directly fans out to OCR + geometry
  (classification and segmentation are removed from the pipeline path).

It also exposes an HTTP debug endpoint that runs the same pipeline on an
ad-hoc upload (useful for local fixtures).
"""
from __future__ import annotations

import base64
import os

from drawing2dxf_common import (
    KafkaProducerClient,
    S3Storage,
    get_logger,
    make_envelope,
    settings,
)
from drawing2dxf_common.schemas import Topics
from drawing2dxf_common.service import make_app, run_consumer_in_thread
from fastapi import HTTPException, UploadFile, File

from .preprocess import preprocess_page

log = get_logger("preprocess")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="preprocess-prod")


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_EXTRACTED or not env.page_id or not env.artifact_uri:
        return

    log.info("preprocessing", page_id=env.page_id, artifact_uri=env.artifact_uri)
    try:
        raw = _storage.get_bytes(env.artifact_uri)
    except Exception as exc:  # noqa: BLE001
        log.error("download failed", error=str(exc))
        raise

    result = preprocess_page(raw)

    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}"
    norm_uri = _storage.put_bytes(f"{base}/normalized.png", result.normalized_png, "image/png")
    bin_uri = _storage.put_bytes(f"{base}/binary.png", result.binary_png, "image/png")
    prv_uri = _storage.put_bytes(f"{base}/preview.jpg", result.preview_jpg, "image/jpeg")

    _update_db(env.page_id, norm_uri, prv_uri, result)

    out = make_envelope(
        Topics.PAGE_PREPROCESSED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload={
            "normalized_uri": norm_uri,
            "binary_uri": bin_uri,
            "preview_uri": prv_uri,
            **result.metadata(),
        },
    )
    _producer.publish(Topics.PAGE_PREPROCESSED, out)

    ocr = make_envelope(
        Topics.PAGE_OCR_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload={"normalized_uri": norm_uri},
    )
    _producer.publish(Topics.PAGE_OCR_REQUESTED, ocr)

    geom = make_envelope(
        Topics.PAGE_GEOMETRY_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload={
            "normalized_uri": norm_uri,
            "binary_uri": bin_uri,
            "page_type": "detail_drawing",
            "dpi": result.quality.estimated_dpi,
            "image_size_px": [result.width, result.height],
        },
    )
    _producer.publish(Topics.PAGE_GEOMETRY_REQUESTED, geom)

    log.info("preprocessed", page_id=env.page_id)


def _update_db(page_id: str, norm_uri: str, prv_uri: str, result) -> None:  # noqa: ANN001
    if not settings.postgres_dsn:
        return
    try:
        import psycopg
    except ImportError:
        log.warning("psycopg not installed; skipping DB update")
        return
    try:
        with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                import json
                cur.execute(
                    """
                    UPDATE pages
                       SET normalized_image_uri = %s,
                           preview_uri = %s,
                           width_px  = COALESCE(NULLIF(%s,0), width_px),
                           height_px = COALESCE(NULLIF(%s,0), height_px),
                           dpi       = COALESCE(dpi, %s),
                           status    = 'preprocessed',
                           metadata  = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                           updated_at = now()
                     WHERE id = %s
                    """,
                    (norm_uri, prv_uri, result.width, result.height, result.quality.estimated_dpi,
                     json.dumps(result.metadata()), page_id),
                )
    except Exception as exc:  # noqa: BLE001
        log.warning("db update skipped", error=str(exc))


# ── FastAPI app ───────────────────────────────────────────────────────────

def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_EXTRACTED],
        group="preprocess-service",
        handler=_handle,
        client_id="preprocess",
    )


app = make_app("preprocess-service", on_startup=_on_startup)


@app.post("/preprocess")
async def http_preprocess(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        result = preprocess_page(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "metadata": result.metadata(),
        "preview_jpg_base64": base64.b64encode(result.preview_jpg).decode("ascii"),
    }

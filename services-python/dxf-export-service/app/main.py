"""DXF export service entry point.

Subscribes to ``page.export.requested``. Pulls CAD JSON from MinIO, generates
DXF and PNG preview, persists both as artifacts and emits ``page.export.done``.
"""
from __future__ import annotations

import json

from drawing2dxf_common import (
    KafkaProducerClient,
    S3Storage,
    get_logger,
    make_envelope,
    settings,
)
from drawing2dxf_common.schemas import Topics
from drawing2dxf_common.service import make_app, run_consumer_in_thread
from fastapi import HTTPException
from pydantic import BaseModel

from .cadjson_to_dxf import cadjson_to_dxf, primitives_summary
from .render_preview import render_preview_png

log = get_logger("dxf")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="dxf-prod")


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_EXPORT_REQUESTED or not env.page_id:
        return
    payload = env.payload or {}
    cad_uri = payload.get("cad_uri") or env.artifact_uri
    if not cad_uri:
        log.warning("missing cad_uri", page_id=env.page_id)
        return

    try:
        cad = json.loads(_storage.get_bytes(cad_uri))
    except Exception as exc:  # noqa: BLE001
        log.error("cannot parse cad json", error=str(exc), page_id=env.page_id)
        return

    version = payload.get("dxf_version") or settings.dxf_default_version
    dxf_bytes = cadjson_to_dxf(cad, version=version, fallback_version=settings.dxf_fallback_version)
    preview_bytes = render_preview_png(cad)

    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}/exports"
    dxf_uri = _storage.put_bytes(f"{base}/page.dxf", dxf_bytes, "application/dxf")
    prv_uri = _storage.put_bytes(f"{base}/page_preview.png", preview_bytes, "image/png")

    _persist(env, dxf_uri, prv_uri, version, primitives_summary(cad.get("primitives", [])))

    log.info("dxf exported", page_id=env.page_id, version=version, bytes=len(dxf_bytes))
    out = make_envelope(
        Topics.PAGE_EXPORT_DONE,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=dxf_uri,
        payload={"dxf_uri": dxf_uri, "preview_uri": prv_uri, "version": version},
    )
    _producer.publish(Topics.PAGE_EXPORT_DONE, out)


def _persist(env, dxf_uri: str, prv_uri: str, version: str, summary: dict) -> None:  # noqa: ANN001
    if not settings.postgres_dsn:
        return
    try:
        import psycopg

        with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn, conn.cursor() as cur:
            for kind, uri in (("dxf", dxf_uri), ("export_preview", prv_uri)):
                cur.execute(
                    """
                    INSERT INTO artifacts (batch_id, page_id, kind, uri, mime_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (env.batch_id, env.page_id, kind, uri,
                     "application/dxf" if kind == "dxf" else "image/png",
                     json.dumps({"dxf_version": version, "summary": summary})),
                )
            cur.execute(
                "UPDATE pages SET status='exported', updated_at=now() WHERE id=%s",
                (env.page_id,),
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("db update skipped", error=str(exc))


def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_EXPORT_REQUESTED],
        group="dxf-export-service",
        handler=_handle,
        client_id="dxf",
    )


app = make_app("dxf-export-service", on_startup=_on_startup)


class ExportRequest(BaseModel):
    cad_json: dict
    version: str | None = None


@app.post("/export")
def http_export(req: ExportRequest) -> dict:
    if not req.cad_json:
        raise HTTPException(status_code=400, detail="cad_json required")
    version = req.version or settings.dxf_default_version
    dxf = cadjson_to_dxf(req.cad_json, version=version, fallback_version=settings.dxf_fallback_version)
    return {"version": version, "bytes": len(dxf)}

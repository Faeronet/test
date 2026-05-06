"""Page router entry point.

Subscribes to ``page.preprocessed``. Selects mock vs. YOLO router based on
``ROUTER_IMPL`` and weights availability, classifies the page, persists the
classification, then publishes either ``page.routed`` (drawings) or
``page.discarded_specification`` (and friends).

Specifications are NOT propagated to segmentation/OCR/geometry/DXF.
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

from .mock_router import MockRouter
from .page_router import PageRouter, RouterResult

log = get_logger("router")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="router-prod")


def _make_router() -> PageRouter:
    if settings.router_impl == "yolo":
        try:
            from .yolo_router_interface import YoloRouter

            router = YoloRouter.from_env()
            log.info("router=yolo loaded", weights=router.weights_path)
            return router
        except FileNotFoundError as exc:
            log.warning("yolo weights missing, falling back to rules", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            log.warning("yolo init failed, falling back to rules", error=str(exc))
    return MockRouter()


_router: PageRouter = _make_router()


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_PREPROCESSED or not env.page_id:
        return

    norm_uri = (env.payload or {}).get("normalized_uri") or env.artifact_uri
    preview_uri = (env.payload or {}).get("preview_uri")
    if not norm_uri:
        log.warning("missing normalized_uri", page_id=env.page_id)
        return

    image = _storage.get_bytes(norm_uri)
    preview = _storage.get_bytes(preview_uri) if preview_uri else None

    result = _router.classify(image, preview=preview)
    log.info(
        "routed",
        page_id=env.page_id,
        page_type=result.page_type,
        confidence=result.confidence,
        reason=result.reason,
    )

    _persist(env.page_id, result)

    if result.page_type == "specification_sheet":
        _producer.publish(
            Topics.PAGE_DISCARDED_SPECIFICATION,
            make_envelope(
                Topics.PAGE_DISCARDED_SPECIFICATION,
                batch_id=env.batch_id,
                file_id=env.file_id,
                page_id=env.page_id,
                payload={**result.to_payload(), "skip_reason": "specification_sheet"},
            ),
        )
        return

    out = make_envelope(
        Topics.PAGE_ROUTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload=result.to_payload(),
    )
    _producer.publish(Topics.PAGE_ROUTED, out)

    # Auto-fan-out: request segmentation + OCR for drawing pages.
    seg = make_envelope(
        Topics.PAGE_SEGMENTATION_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload=result.to_payload() | {"binary_uri": (env.payload or {}).get("binary_uri")},
    )
    _producer.publish(Topics.PAGE_SEGMENTATION_REQUESTED, seg)

    ocr = make_envelope(
        Topics.PAGE_OCR_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload=result.to_payload(),
    )
    _producer.publish(Topics.PAGE_OCR_REQUESTED, ocr)


def _persist(page_id: str, result: RouterResult) -> None:
    if not settings.postgres_dsn:
        return
    try:
        import psycopg

        with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO page_classifications (page_id, page_type, confidence, reason, model_version)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (page_id, result.page_type, result.confidence, result.reason, result.model_version),
            )
            new_status = "routed" if result.page_type != "specification_sheet" else "skipped"
            skip_reason = "specification_sheet" if result.page_type == "specification_sheet" else None
            cur.execute(
                """
                UPDATE pages SET page_type=%s, confidence=%s, status=%s,
                                 skip_reason=%s, updated_at=now()
                WHERE id=%s
                """,
                (result.page_type, result.confidence, new_status, skip_reason, page_id),
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("db update skipped", error=str(exc))


# ── FastAPI app ─────────────────────────────────────────────────────────

def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_PREPROCESSED],
        group="router-service",
        handler=_handle,
        client_id="router",
    )


app = make_app("model-router-service", on_startup=_on_startup)


@app.get("/router/info")
def info() -> dict:
    return {"impl": settings.router_impl, "active": type(_router).__name__}

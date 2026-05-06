"""Geometry service entry point.

Subscribes to ``page.geometry.requested``. Pulls optional segmentation masks
and (optionally) OCR blocks from MinIO, runs the geometry restoration
pipeline, persists ``cad_json.json`` and emits both ``page.geometry.done`` and
``page.qa.requested``.
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

from .cadjson_builder import build_cad_json

log = get_logger("geometry")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="geom-prod")


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_GEOMETRY_REQUESTED or not env.page_id:
        return
    payload = env.payload or {}
    mask_uris = payload.get("mask_uris") or {}
    visible_uri = mask_uris.get("visible_geometry")
    visible = None
    if visible_uri:
        visible = _storage.get_bytes(visible_uri)
    else:
        # Segmentation is optional: derive visible geometry from binary fallback.
        visible = _resolve_visible_from_binary(payload)
        if not visible:
            log.warning("missing visible source (mask or binary)", page_id=env.page_id)
            return
    centerline = _maybe(mask_uris.get("centerline"))
    dimension = _maybe(mask_uris.get("dimension_graphics"))
    break_m = _maybe(mask_uris.get("break_symbol"))
    text = _maybe(mask_uris.get("text"))
    frame = _maybe(mask_uris.get("frame_titleblock"))

    ocr_blocks = _maybe_ocr(env)

    page_type = payload.get("page_type") or "detail_drawing"
    cad = build_cad_json(
        visible_mask=visible,
        page_id=env.page_id,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_type=page_type,
        centerline_mask=centerline,
        dimension_mask=dimension,
        break_mask=break_m,
        text_mask=text,
        frame_mask=frame,
        ocr_blocks=ocr_blocks,
        image_size=tuple(payload.get("image_size_px") or ()) or None,
        dpi=payload.get("dpi"),
    )

    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}"
    cad_uri = _storage.put_bytes(
        f"{base}/cad.json",
        json.dumps(cad, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )

    log.info(
        "geometry done",
        page_id=env.page_id,
        primitives=len(cad["primitives"]),
        requires_review=cad["qa"]["requires_review"],
    )
    out = make_envelope(
        Topics.PAGE_GEOMETRY_DONE,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=cad_uri,
        payload={
            "primitives": len(cad["primitives"]),
            "cad_uri": cad_uri,
            "qa": cad["qa"],
        },
    )
    _producer.publish(Topics.PAGE_GEOMETRY_DONE, out)

    qa_req = make_envelope(
        Topics.PAGE_QA_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=cad_uri,
        payload={"cad_uri": cad_uri, "normalized_uri": payload.get("normalized_uri")},
    )
    _producer.publish(Topics.PAGE_QA_REQUESTED, qa_req)


def _maybe(uri: str | None) -> bytes | None:
    if not uri:
        return None
    try:
        return _storage.get_bytes(uri)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not fetch mask", uri=uri, error=str(exc))
        return None


def _maybe_ocr(env) -> list | None:  # noqa: ANN001
    """OCR is asynchronous: we may have it ready, or not. We look it up
    lazily by convention from the canonical key path."""
    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}"
    uri = _storage.uri(f"{base}/ocr_blocks.json")
    if not _storage.exists(uri):
        return None
    try:
        return json.loads(_storage.get_bytes(uri))
    except Exception:  # noqa: BLE001
        return None


def _resolve_visible_from_binary(payload: dict) -> bytes | None:
    binary_uri = payload.get("binary_uri")
    if not binary_uri:
        return None
    try:
        return _storage.get_bytes(binary_uri)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not fetch binary fallback", uri=binary_uri, error=str(exc))
        return None


def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_GEOMETRY_REQUESTED],
        group="geometry-service",
        handler=_handle,
        client_id="geometry",
    )


app = make_app("geometry-service", on_startup=_on_startup)

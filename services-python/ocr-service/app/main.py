"""OCR service entry point.

Subscribes to ``page.ocr.requested`` and emits ``page.ocr.done``. Stores OCR
blocks as a JSON artifact (``ocr_blocks.json``) in MinIO and as rows in the
``ocr_blocks`` table.

Even with the mock backend (returns no blocks), this keeps the dimension
parser available via the HTTP endpoint ``POST /parse-dimension``.
"""
from __future__ import annotations

import json
import uuid

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

from .dimension_parser import parse_dimension
from .gost_parser import parse_gost_block
from .mock_ocr import MockOCR

log = get_logger("ocr")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="ocr-prod")


def _make_backend():
    if settings.ocr_impl == "paddle":
        try:
            from .paddleocr_interface import PaddleOCRBackend

            return PaddleOCRBackend.from_env()
        except FileNotFoundError as exc:
            log.warning("paddle weights missing, falling back", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            log.warning("paddle init failed, falling back", error=str(exc))
    return MockOCR()


_backend = _make_backend()


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_OCR_REQUESTED or not env.page_id:
        return
    if not env.artifact_uri:
        log.warning("ocr requested without artifact", page_id=env.page_id)
        return

    image = _storage.get_bytes(env.artifact_uri)
    raw_blocks = _backend.detect(image)

    enriched = []
    for blk in raw_blocks:
        text = blk.get("text", "")
        kind = blk.get("kind", "unknown")
        parsed = blk.get("parsed")
        if not parsed:
            if kind == "dimension_text" or _looks_like_dimension(text):
                parsed = parse_dimension(text).to_dict()
                kind = kind if kind != "unknown" else "dimension_text"
            elif kind == "titleblock_text":
                parsed = parse_gost_block(text)
        enriched.append(
            {
                "id": blk.get("id", str(uuid.uuid4())),
                "text": text,
                "bbox_px": blk.get("bbox_px") or [0, 0, 0, 0],
                "rotation_deg": blk.get("rotation_deg", 0.0),
                "confidence": float(blk.get("confidence", 0.0)),
                "kind": kind,
                "parsed": parsed,
            }
        )

    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}"
    json_uri = _storage.put_bytes(
        f"{base}/ocr_blocks.json",
        json.dumps(enriched, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )

    log.info("ocr done", page_id=env.page_id, blocks=len(enriched))
    out = make_envelope(
        Topics.PAGE_OCR_DONE,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=json_uri,
        payload={"blocks": len(enriched), "ocr_uri": json_uri},
    )
    _producer.publish(Topics.PAGE_OCR_DONE, out)


def _looks_like_dimension(text: str) -> bool:
    if not text:
        return False
    sample = text.strip()
    return any(token in sample for token in ("Ø", "Ф", "R", "M", "±", "°", "x", "X", "×"))


def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_OCR_REQUESTED],
        group="ocr-service",
        handler=_handle,
        client_id="ocr",
    )


app = make_app("ocr-service", on_startup=_on_startup)


class DimensionRequest(BaseModel):
    text: str


@app.post("/parse-dimension")
def http_parse_dimension(req: DimensionRequest) -> dict:
    if not req.text:
        raise HTTPException(status_code=400, detail="text required")
    return parse_dimension(req.text).to_dict()


@app.get("/ocr/info")
def info() -> dict:
    return {"impl": settings.ocr_impl, "active": type(_backend).__name__}

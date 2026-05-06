"""QA service entry point.

Subscribes to ``page.qa.requested``. Pulls CAD JSON + binarised source page,
rasterises CAD, computes IoU/chamfer/Hausdorff, builds an overlay PNG and a
heatmap PNG, persists everything in MinIO and PostgreSQL, then publishes
``page.qa.done`` and (if applicable) ``page.review.required`` and
``page.export.requested``.
"""
from __future__ import annotations

import json

import cv2
import numpy as np
from drawing2dxf_common import (
    KafkaProducerClient,
    S3Storage,
    get_logger,
    make_envelope,
    settings,
)
from drawing2dxf_common.schemas import Topics
from drawing2dxf_common.service import make_app, run_consumer_in_thread

from .compare import chamfer_distance, hausdorff_distance, heatmap, raster_iou
from .metrics import QAReport, review_required
from .rasterize import rasterise

log = get_logger("qa")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="qa-prod")


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_QA_REQUESTED or not env.page_id:
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

    image_size = cad.get("document", {}).get("image_size_px") or [2480, 3508]
    primitives = cad.get("primitives", [])
    cad_raster = rasterise(primitives, (int(image_size[0]), int(image_size[1])))

    binary_uri = _binary_uri(env, payload)
    iou = chamfer = hd = float("nan")
    overlay_uri = heatmap_uri = None
    if binary_uri and _storage.exists(binary_uri):
        bin_bytes = _storage.get_bytes(binary_uri)
        bin_img = cv2.imdecode(np.frombuffer(bin_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if bin_img is not None:
            if bin_img.shape[:2] != cad_raster.shape[:2]:
                cad_raster = cv2.resize(cad_raster, (bin_img.shape[1], bin_img.shape[0]), interpolation=cv2.INTER_NEAREST)
            iou = raster_iou(cad_raster, bin_img)
            chamfer = chamfer_distance(cad_raster, bin_img)
            hd = hausdorff_distance(cad_raster, bin_img)
            overlay = _make_overlay(bin_img, cad_raster)
            heat = heatmap(cad_raster, bin_img)

            base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}/qa"
            overlay_uri = _storage.put_bytes(f"{base}/overlay.png", _png(overlay), "image/png")
            heatmap_uri = _storage.put_bytes(f"{base}/heatmap.png", _png(heat), "image/png")

    low_conf = sum(1 for p in primitives if (p.get("confidence") or 1.0) < 0.55)
    page_type = cad.get("document", {}).get("page_type") or "unknown"
    review, warnings = review_required(
        raster_iou=float(iou) if iou == iou else 0.0,
        chamfer_px=float(chamfer) if chamfer != float("inf") and chamfer == chamfer else 0.0,
        hausdorff_px=float(hd) if hd != float("inf") and hd == hd else 0.0,
        low_confidence_count=low_conf,
        page_type=page_type,
    )

    report = QAReport(
        raster_iou=float(iou) if iou == iou else 0.0,
        chamfer_px=float(chamfer) if chamfer != float("inf") and chamfer == chamfer else 0.0,
        hausdorff_px=float(hd) if hd != float("inf") and hd == hd else 0.0,
        primitive_count=len(primitives),
        low_confidence_count=low_conf,
        requires_review=review,
        warnings=warnings,
    )

    _persist(env.page_id, report)

    out = make_envelope(
        Topics.PAGE_QA_DONE,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=cad_uri,
        payload={
            **report.to_dict(),
            "overlay_uri": overlay_uri,
            "heatmap_uri": heatmap_uri,
        },
    )
    _producer.publish(Topics.PAGE_QA_DONE, out)

    if review:
        _producer.publish(
            Topics.PAGE_REVIEW_REQUIRED,
            make_envelope(
                Topics.PAGE_REVIEW_REQUIRED,
                batch_id=env.batch_id,
                file_id=env.file_id,
                page_id=env.page_id,
                payload=report.to_dict(),
            ),
        )

    # In MVP we still queue the export — the reviewer can re-export later.
    _producer.publish(
        Topics.PAGE_EXPORT_REQUESTED,
        make_envelope(
            Topics.PAGE_EXPORT_REQUESTED,
            batch_id=env.batch_id,
            file_id=env.file_id,
            page_id=env.page_id,
            artifact_uri=cad_uri,
            payload={"cad_uri": cad_uri, "dxf_version": settings.dxf_default_version},
        ),
    )


def _binary_uri(env, payload):  # noqa: ANN001
    if "binary_uri" in payload:
        return payload["binary_uri"]
    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}"
    return _storage.uri(f"{base}/binary.png")


def _make_overlay(bin_img: np.ndarray, cad_raster: np.ndarray) -> np.ndarray:
    bg = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)
    overlay = bg.copy()
    overlay[cad_raster > 0] = (0, 255, 0)
    blended = cv2.addWeighted(bg, 0.5, overlay, 0.5, 0)
    return blended


def _png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise RuntimeError("png encoding failed")
    return buf.tobytes()


def _persist(page_id: str, report: QAReport) -> None:
    if not settings.postgres_dsn:
        return
    try:
        import psycopg

        with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO qa_metrics (page_id, chamfer_px, hausdorff_px, raster_iou, requires_review, warnings, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    page_id,
                    report.chamfer_px,
                    report.hausdorff_px,
                    report.raster_iou,
                    report.requires_review,
                    json.dumps(report.warnings),
                    json.dumps({"primitive_count": report.primitive_count, "low_confidence_count": report.low_confidence_count}),
                ),
            )
            new_status = "review_required" if report.requires_review else "qa_done"
            cur.execute(
                "UPDATE pages SET status=%s, updated_at=now() WHERE id=%s",
                (new_status, page_id),
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("db update skipped", error=str(exc))


def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_QA_REQUESTED],
        group="qa-service",
        handler=_handle,
        client_id="qa",
    )


app = make_app("qa-service", on_startup=_on_startup)

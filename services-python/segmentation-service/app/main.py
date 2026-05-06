"""Segmentation service entry point.

Subscribes to ``page.segmentation.requested``. Selects classical vs YOLO
implementation, computes masks, uploads PNG masks to MinIO under
``pages/<batch>/<file>/<page>/masks/<class>.png`` and emits
``page.segmentation.done``.

After publishing ``page.segmentation.done`` we also emit
``page.geometry.requested`` to advance the pipeline. Geometry-service uses the
masks to fit primitives.
"""
from __future__ import annotations

from drawing2dxf_common import (
    KafkaProducerClient,
    S3Storage,
    get_logger,
    make_envelope,
    settings,
)
from drawing2dxf_common.schemas import Topics
from drawing2dxf_common.service import make_app, run_consumer_in_thread

from .masks import MaskBundle
from .mock_segmenter import MockSegmenter

log = get_logger("segmentation")

_storage = S3Storage.from_settings(settings)
_producer = KafkaProducerClient(settings.kafka_brokers, client_id="seg-prod")


def _make_segmenter():
    if settings.seg_impl == "yolo":
        try:
            from .yolo11_segmenter_interface import Yolo11Segmenter

            seg = Yolo11Segmenter.from_env()
            log.info("segmenter=yolo loaded", weights=seg.weights_path)
            return seg
        except FileNotFoundError as exc:
            log.warning("yolo seg weights missing, falling back", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            log.warning("yolo seg init failed, falling back", error=str(exc))
    return MockSegmenter()


_segmenter = _make_segmenter()


def _handle(topic: str, env) -> None:  # noqa: ANN001
    if topic != Topics.PAGE_SEGMENTATION_REQUESTED or not env.page_id:
        return

    norm_uri = env.artifact_uri or (env.payload or {}).get("normalized_uri")
    binary_uri = (env.payload or {}).get("binary_uri")
    if not norm_uri:
        log.warning("missing normalized_uri", page_id=env.page_id)
        return

    image = _storage.get_bytes(norm_uri)
    binary = _storage.get_bytes(binary_uri) if binary_uri else None

    bundle: MaskBundle = _segmenter.segment(image, binary_image=binary)

    base = f"pages/{env.batch_id or 'unknown'}/{env.file_id or 'unknown'}/{env.page_id}/masks"
    mask_uris: dict[str, str] = {}
    for cls_name, mask in bundle.masks.items():
        uri = _storage.put_bytes(f"{base}/{cls_name}.png", mask.png_bytes, "image/png")
        mask_uris[cls_name] = uri

    log.info(
        "segmented",
        page_id=env.page_id,
        classes=len(mask_uris),
        impl=type(_segmenter).__name__,
    )

    out = make_envelope(
        Topics.PAGE_SEGMENTATION_DONE,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload={
            "mask_uris": mask_uris,
            **bundle.to_payload(),
        },
    )
    _producer.publish(Topics.PAGE_SEGMENTATION_DONE, out)

    geom = make_envelope(
        Topics.PAGE_GEOMETRY_REQUESTED,
        batch_id=env.batch_id,
        file_id=env.file_id,
        page_id=env.page_id,
        artifact_uri=norm_uri,
        payload={
            "normalized_uri": norm_uri,
            "binary_uri": binary_uri,
            "mask_uris": mask_uris,
            **bundle.to_payload(),
        },
    )
    _producer.publish(Topics.PAGE_GEOMETRY_REQUESTED, geom)


def _on_startup(app):  # noqa: ANN001
    _storage.ensure_bucket()
    app.state.consumer = run_consumer_in_thread(
        topics=[Topics.PAGE_SEGMENTATION_REQUESTED],
        group="segmentation-service",
        handler=_handle,
        client_id="segmentation",
    )


app = make_app("segmentation-service", on_startup=_on_startup)


@app.get("/segmenter/info")
def info() -> dict:
    return {"impl": settings.seg_impl, "active": type(_segmenter).__name__}

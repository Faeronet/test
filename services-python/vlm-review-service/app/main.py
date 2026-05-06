"""VLM review-helper service (placeholder).

Exposes ``POST /review`` with a CAD JSON payload. Returns a small natural
language summary. This service is **not** wired into the Kafka pipeline by
default — it is invoked on-demand from the web review page.
"""
from __future__ import annotations

from drawing2dxf_common import get_logger, settings
from drawing2dxf_common.service import make_app
from pydantic import BaseModel

from .mock_vlm import MockVLM

log = get_logger("vlm")


def _make_backend():
    if settings.vlm_impl == "qwen":
        try:
            from .qwen25vl_interface import QwenVLM

            return QwenVLM.from_env()
        except FileNotFoundError as exc:
            log.warning("qwen weights missing", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            log.warning("qwen init failed", error=str(exc))
    return MockVLM()


_backend = _make_backend()

app = make_app("vlm-review-service")


class ReviewRequest(BaseModel):
    cad_json: dict
    image_uri: str | None = None


@app.post("/review")
def http_review(req: ReviewRequest) -> dict:
    return _backend.review(req.cad_json, image_uri=req.image_uri)


@app.get("/vlm/info")
def info() -> dict:
    return {"impl": settings.vlm_impl, "active": type(_backend).__name__}

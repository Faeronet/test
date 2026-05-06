"""SAM 2.1 interactive-mask service (placeholder)."""
from __future__ import annotations

from drawing2dxf_common import get_logger, settings
from drawing2dxf_common.service import make_app
from pydantic import BaseModel

from .mock_sam import MockSAM

log = get_logger("sam")


def _make_backend():
    if settings.sam_impl == "sam21":
        try:
            from .sam21_interface import SAM21

            return SAM21.from_env()
        except FileNotFoundError as exc:
            log.warning("sam weights missing", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            log.warning("sam init failed", error=str(exc))
    return MockSAM()


_backend = _make_backend()

app = make_app("sam-assist-service")


class PredictRequest(BaseModel):
    image_uri: str
    points: list[list[float]] | None = None
    box: list[float] | None = None


@app.post("/predict")
def http_predict(req: PredictRequest) -> dict:
    return _backend.predict_mask(image_uri=req.image_uri, points=req.points, box=req.box)


@app.get("/sam/info")
def info() -> dict:
    return {"impl": settings.sam_impl, "active": type(_backend).__name__}

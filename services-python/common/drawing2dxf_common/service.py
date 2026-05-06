"""Tiny FastAPI scaffolding shared by every Python service.

Every service mounts:
* `GET  /healthz`  → `{"status":"ok"}`
* `GET  /readyz`   → `{"status":"ready"}`
* `GET  /metrics`  → prometheus exposition

Services additionally register a Kafka consumer thread via :func:`run_consumer_in_thread`.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from typing import Callable, Iterable, Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import settings
from .kafka_client import Handler, KafkaConsumerClient, KafkaProducerClient
from .logging import get_logger

log = get_logger("service")


def make_app(name: str, on_startup: Optional[Callable[[FastAPI], None]] = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: D401, ANN001
        if on_startup is not None:
            on_startup(app)
        yield

    app = FastAPI(title=name, lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict:  # noqa: D401
        return {"status": "ok", "service": name}

    @app.get("/readyz")
    def readyz() -> dict:  # noqa: D401
        return {"status": "ready", "service": name}

    @app.get("/metrics")
    def metrics() -> PlainTextResponse:  # noqa: D401
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


def run_consumer_in_thread(
    topics: Iterable[str],
    group: str,
    handler: Handler,
    *,
    client_id: Optional[str] = None,
    daemon: bool = True,
) -> threading.Thread:
    """Spin up a background thread running a Kafka consumer.

    Returns the thread (already started). The caller must keep its reference
    alive (e.g. by storing it on `app.state`).
    """

    def _loop() -> None:
        producer = KafkaProducerClient(settings.kafka_brokers, client_id=(client_id or group) + "-dlq")
        consumer = KafkaConsumerClient(
            settings.kafka_brokers,
            group=group,
            topics=topics,
            client_id=client_id,
        )
        log.info("consumer started", group=group, topics=list(topics))
        try:
            consumer.consume(handler, producer_for_dlq=producer)
        except Exception as exc:  # noqa: BLE001
            log.exception("consumer crashed", error=str(exc))
        finally:
            consumer.close()
            producer.close()

    t = threading.Thread(target=_loop, name=f"kafka-consumer-{group}", daemon=daemon)
    t.start()
    return t

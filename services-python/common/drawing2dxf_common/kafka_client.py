"""Tiny wrappers around confluent-kafka.

`KafkaProducerClient.publish(topic, env)` synchronously delivers an envelope.
`KafkaConsumerClient.consume(topics, handler, ...)` runs a polling loop with
idempotency keyed on (page_id, event_type).

Each Python service uses these to plug into the same Kafka topology described
in `configs/topics.yaml`.
"""
from __future__ import annotations

import json
import time
from typing import Callable, Iterable, List, Optional

from confluent_kafka import Consumer, KafkaError, Producer

from .logging import get_logger
from .schemas import Envelope, Topics

log = get_logger("kafka")

Handler = Callable[[str, Envelope], None]


class KafkaProducerClient:
    def __init__(self, brokers: List[str], client_id: str = "drawing2dxf-py") -> None:
        self._cl = Producer(
            {
                "bootstrap.servers": ",".join(brokers),
                "client.id": client_id,
                "enable.idempotence": True,
                "linger.ms": 5,
                "compression.type": "lz4",
            }
        )

    def publish(self, topic: str, env: Envelope, *, flush: bool = True) -> None:
        body = env.to_bytes()
        self._cl.produce(topic=topic, key=env.key().encode("utf-8"), value=body)
        if flush:
            self._cl.flush(timeout=5.0)

    def close(self) -> None:
        self._cl.flush(5.0)


class KafkaConsumerClient:
    def __init__(
        self,
        brokers: List[str],
        group: str,
        topics: Iterable[str],
        client_id: Optional[str] = None,
    ) -> None:
        self._cl = Consumer(
            {
                "bootstrap.servers": ",".join(brokers),
                "group.id": group,
                "client.id": client_id or group,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "session.timeout.ms": 45000,
                "max.poll.interval.ms": 600000,
            }
        )
        self._topics = list(topics)
        self._cl.subscribe(self._topics)

    def consume(
        self,
        handler: Handler,
        *,
        producer_for_dlq: Optional[KafkaProducerClient] = None,
        max_attempts: int = 5,
        idle_sleep: float = 0.2,
    ) -> None:
        while True:
            msg = self._cl.poll(timeout=1.0)
            if msg is None:
                time.sleep(idle_sleep)
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.warning("kafka error", error=str(msg.error()))
                continue

            value = msg.value()
            if value is None:
                self._cl.commit(asynchronous=False)
                continue
            try:
                env = Envelope.model_validate_json(value)
            except Exception as exc:  # noqa: BLE001
                log.error("invalid envelope", error=str(exc))
                if producer_for_dlq is not None:
                    fallback = Envelope(
                        event_type="deadletter.malformed",
                        payload={"raw": value.decode("utf-8", errors="replace"), "error": str(exc)},
                    )
                    producer_for_dlq.publish(Topics.DEADLETTER, fallback)
                self._cl.commit(asynchronous=False)
                continue

            try:
                handler(msg.topic(), env)
                self._cl.commit(asynchronous=False)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "handler failed",
                    topic=msg.topic(),
                    event_id=env.event_id,
                    attempt=env.attempt,
                    error=str(exc),
                )
                if env.attempt >= max_attempts and producer_for_dlq is not None:
                    dl = Envelope(
                        event_type="deadletter",
                        batch_id=env.batch_id,
                        file_id=env.file_id,
                        page_id=env.page_id,
                        payload={
                            "original_topic": msg.topic(),
                            "original_event": env.model_dump(),
                            "error": str(exc),
                        },
                    )
                    producer_for_dlq.publish(Topics.DEADLETTER, dl)
                    self._cl.commit(asynchronous=False)
                # otherwise leave uncommitted -> redelivery

    def close(self) -> None:
        self._cl.close()

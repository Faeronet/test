"""drawing2dxf shared utilities.

Heavy / optional submodules (kafka, storage) are imported lazily so that
unit-test environments without librdkafka or minio still import
``drawing2dxf_common.schemas`` cleanly.
"""

from .config import Settings, settings
from .schemas import Envelope, make_envelope
from .logging import get_logger


def __getattr__(name):  # noqa: D401, ANN001
    if name == "KafkaProducerClient":
        from .kafka_client import KafkaProducerClient as cls
        return cls
    if name == "KafkaConsumerClient":
        from .kafka_client import KafkaConsumerClient as cls
        return cls
    if name == "S3Storage":
        from .storage import S3Storage as cls
        return cls
    raise AttributeError(name)


__all__ = [
    "Settings",
    "settings",
    "KafkaProducerClient",
    "KafkaConsumerClient",
    "S3Storage",
    "Envelope",
    "make_envelope",
    "get_logger",
]

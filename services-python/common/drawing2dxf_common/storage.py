"""Thin wrapper over the MinIO Python SDK that uses canonical s3:// URIs."""
from __future__ import annotations

import io
import os
import re
from typing import BinaryIO, Optional

from minio import Minio
from minio.error import S3Error


_S3_URI_RE = re.compile(r"^s3://(?P<bucket>[^/]+)/(?P<key>.+)$")


class S3Storage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        region: str = "us-east-1",
    ):
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure, region=region
        )
        self.bucket = bucket
        self.region = region

    @classmethod
    def from_settings(cls, settings) -> "S3Storage":
        return cls(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_use_ssl,
            region=settings.minio_region,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket, location=self.region)

    # ── url helpers ───────────────────────────────────────────────────

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key.lstrip('/')}"

    def parse_uri(self, uri_or_key: str) -> str:
        m = _S3_URI_RE.match(uri_or_key)
        if m:
            if m.group("bucket") != self.bucket:
                raise ValueError(f"bucket mismatch: {m.group('bucket')} != {self.bucket}")
            return m.group("key")
        return uri_or_key.lstrip("/")

    # ── i/o ────────────────────────────────────────────────────────────

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return self.uri(key)

    def put_stream(self, key: str, data: BinaryIO, length: int, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket, key, data, length=length, content_type=content_type
        )
        return self.uri(key)

    def get_bytes(self, uri_or_key: str) -> bytes:
        key = self.parse_uri(uri_or_key)
        resp = self.client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def download_to(self, uri_or_key: str, path: str) -> str:
        key = self.parse_uri(uri_or_key)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.client.fget_object(self.bucket, key, path)
        return path

    def exists(self, uri_or_key: str) -> bool:
        key = self.parse_uri(uri_or_key)
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False

    def presign_get(self, uri_or_key: str, expires_seconds: int = 900) -> str:
        from datetime import timedelta

        key = self.parse_uri(uri_or_key)
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires_seconds)
        )

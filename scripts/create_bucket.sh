#!/usr/bin/env bash
# Create the MinIO bucket configured in .env. Run from the project root.
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
ACCESS="${MINIO_ACCESS_KEY:-drawing2dxf}"
SECRET="${MINIO_SECRET_KEY:-drawing2dxf-secret}"
BUCKET="${MINIO_BUCKET:-drawing2dxf}"

# If a containerised mc is available, use it; otherwise fall back to host mc.
if docker compose ps minio >/dev/null 2>&1; then
  echo "==> creating bucket via containerised mc"
  docker run --rm --network host \
      --entrypoint /bin/sh \
      minio/mc:latest -c "\
          mc alias set local http://${ENDPOINT} ${ACCESS} ${SECRET} && \
          mc mb --ignore-existing local/${BUCKET} && \
          mc anonymous set download local/${BUCKET} || true"
else
  command -v mc >/dev/null 2>&1 || { echo "mc not found; install MinIO client"; exit 1; }
  mc alias set local "http://${ENDPOINT}" "${ACCESS}" "${SECRET}"
  mc mb --ignore-existing "local/${BUCKET}"
  mc anonymous set download "local/${BUCKET}" || true
fi

echo "==> bucket ${BUCKET} ready"

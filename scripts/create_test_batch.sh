#!/usr/bin/env bash
# Create a fresh batch and upload one or more files into it.
# Usage:
#   ./scripts/create_test_batch.sh path/to/file1.pdf path/to/file2.png
set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
BATCH_NAME="${BATCH_NAME:-cli-batch-$(date +%Y%m%d%H%M%S)}"

if [[ $# -eq 0 ]]; then
  echo "usage: $0 <file> [<file> ...]" >&2
  exit 2
fi

batch=$(curl -fsS -H "Content-Type: application/json" \
              -X POST "${API_URL}/api/batches" \
              -d "{\"name\": \"${BATCH_NAME}\"}" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
echo "batch_id=${batch}"

for f in "$@"; do
  echo "uploading ${f}"
  curl -fsS -F "files=@${f}" "${API_URL}/api/batches/${batch}/upload" | head -c 400; echo
done

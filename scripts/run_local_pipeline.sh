#!/usr/bin/env bash
# Drive the full local pipeline end-to-end:
#   1. Generate a synthetic test image fixture if none is bundled.
#   2. Create a batch via API.
#   3. Upload the fixture.
#   4. Wait until the page reaches `exported` (or review_required) status.
#   5. Print the resulting DXF artifact URL.
set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
FIXTURE_DIR="${FIXTURE_DIR:-tests/fixtures/sample_inputs}"
FIXTURE="${FIXTURE_DIR}/synthetic_drawing.png"

mkdir -p "${FIXTURE_DIR}"

if [[ ! -f "${FIXTURE}" ]]; then
  echo "==> generating synthetic fixture"
  python3 - <<'PY'
import os
from PIL import Image, ImageDraw

os.makedirs("tests/fixtures/sample_inputs", exist_ok=True)
img = Image.new("L", (1240, 1754), 255)  # ~A4 @150dpi
d = ImageDraw.Draw(img)

# outer frame
d.rectangle([60, 60, 1180, 1694], outline=0, width=3)
# titleblock
d.rectangle([700, 1500, 1180, 1694], outline=0, width=2)
d.text((720, 1520), "DRAWING_NO 0001", fill=0)
d.text((720, 1540), "GOST 2.109-73", fill=0)

# part: rectangle + circle + arc-like
d.rectangle([300, 400, 900, 800], outline=0, width=4)
d.ellipse([520, 540, 680, 700], outline=0, width=4)
d.arc([200, 900, 600, 1300], start=180, end=360, fill=0, width=4)
# centerline
for x in range(200, 950, 20):
    d.line([(x, 600), (x + 10, 600)], fill=0, width=2)

img.save("tests/fixtures/sample_inputs/synthetic_drawing.png")
print("wrote tests/fixtures/sample_inputs/synthetic_drawing.png")
PY
fi

echo "==> creating batch"
batch=$(curl -fsS -H "Content-Type: application/json" \
              -X POST "${API_URL}/api/batches" \
              -d '{"name":"local-pipeline"}' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
echo "batch_id=${batch}"

echo "==> uploading fixture"
curl -fsS -F "files=@${FIXTURE}" "${API_URL}/api/batches/${batch}/upload" >/dev/null
echo "==> waiting for processing (max 90s)"
for i in $(seq 1 90); do
  sleep 1
  state=$(curl -fsS "${API_URL}/api/batches/${batch}")
  if echo "$state" | grep -q '"status":"exported"'; then
    echo "==> exported"
    break
  fi
  if [[ $((i % 10)) -eq 0 ]]; then
    echo "  ... still processing (${i}s)"
  fi
done

echo "==> requesting export"
curl -fsS -H "Content-Type: application/json" -X POST \
     "${API_URL}/api/batches/${batch}/export" \
     -d '{"format":"zip"}'

echo
echo "==> done. Open http://localhost:5173/batches/${batch}"

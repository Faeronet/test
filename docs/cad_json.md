# CAD JSON v0.1

CAD JSON — промежуточное представление между geometry-service и
dxf-export-service. Validated by `packages/schemas/cadjson.schema.json` и
зеркальными pydantic-моделями в
`services-python/common/drawing2dxf_common/schemas.py`.

## Структура

```jsonc
{
  "schema_version": "0.1",
  "document": {
    "batch_id": "uuid",
    "file_id": "uuid",
    "page_id": "uuid",
    "units": "mm",
    "dpi": 300,
    "px_per_mm": 11.811,
    "page_type": "detail_drawing",
    "image_size_px": [2480, 3508]
  },
  "layers": [
    {"name": "02_PART_VISIBLE", "role": "geometry"},
    ...
  ],
  "primitives": [
    {
      "id": "ln_0001",
      "type": "LINE",          // LINE | ARC | CIRCLE | LWPOLYLINE | TEXT
      "layer": "02_PART_VISIBLE",
      "p1": [0.0, 0.0],
      "p2": [100.0, 0.0],
      "confidence": 0.92,
      "fit": {"method": "ransac_tls", "rms_px": 1.1, "inliers": 84},
      "source_pixels": 84,
      "warnings": []
    }
  ],
  "ocr": [
    {
      "id": "ocr_0001",
      "text": "Ø40H11",
      "bbox_px": [120, 540, 220, 580],
      "rotation_deg": 0.0,
      "confidence": 0.91,
      "kind": "dimension_text",
      "parsed": {"kind": "diameter", "value": 40.0, "unit": "mm", "tolerance": "H11"}
    }
  ],
  "dimensions": [],
  "constraints": [],
  "qa": {
    "requires_review": false,
    "warnings": [],
    "raster_iou": 0.91,
    "chamfer_px": 1.4
  }
}
```

## Ключевые правила

* **Координаты в пикселях исходного скана.** dxf-export-service сам
  переводит их в миллиметры через `px_per_mm` и переворачивает Y-ось
  (DXF Y растёт вверх, raster Y — вниз).
* **`confidence` всегда в `[0, 1]`.** Низкая уверенность (<0.5) перекрывает
  присвоение слоя на `90_QA_LOW_CONFIDENCE`.
* **`fit.method` — свободная строка** (`ransac_tls`, `kasa_ls`, `contour`,
  `ransac_arc`), удобная для отладки.
* **`primitives` — только примитивы CAD.** Никаких raster-контуров «на
  всякий случай»; if-в сомнениях — кладите на QA-слой.
* **`ocr` опционален**, geometry-service не падает, если OCR пуст.

## Round-trip

`cadjson_to_dxf` сохраняет исходный layer в DXF-XDATA, чтобы при будущем
обратном импорте (DXF → CAD JSON) можно было восстановить класс
примитива даже после пометки на `90_QA_LOW_CONFIDENCE`.

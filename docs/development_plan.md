# Roadmap

## v0.1 — Skeleton (текущий статус)

* Полный monorepo (Go API + workers + 9 Python services + React UI).
* Mock/classical pipeline `image → CAD JSON → DXF` без обученных моделей.
* PostgreSQL + MinIO + Redpanda поднимаются одной командой.
* Безопасный ingest: PDF, изображения, ZIP/RAR/7Z/TAR/.gz/.bz2/.xz.
* Rule-based page router отбрасывает спецификации.
* RANSAC LINE / KASA CIRCLE / ARC fitting.
* QA: raster IoU, chamfer, hausdorff, heatmap.
* Реальный DXF R2010/R2000 через ezdxf.
* SSE progress в web-UI.

## v0.2 — Plug-in моделей

* YOLO11s-cls page router → точная классификация detail vs assembly.
* PaddleOCR PP-OCRv5 → реальный OCR с поддержкой кириллицы.
* Замена `MockSegmenter` → `Yolo11Segmenter` (после получения весов).
* Tile-based segmentation, SAHI-style merge.

## v0.3 — Качество геометрии

* Native DIMENSION entities в DXF (DIMSTYLE per КОМПАС).
* Detection of:
  * tangent / perpendicular / parallel constraints;
  * concentric circle pairs (внутренний/внешний диаметры);
  * symmetric mirror lines.
* Полноценная hatch-detection и заливка через DXF HATCH.
* Поддержка hidden line type detection из dash-stride.

## v0.4 — UI

* Inline-редактирование примитивов (drag endpoints, change layer).
* Подсказки от Qwen2.5-VL для подозрительных страниц.
* SAM 2.1 interactive mask refinement при низкой уверенности
  segmentation.
* Heatmap overlays поверх Konva canvas (сейчас только thumbnail).

## v0.5 — Production

* Auth (OIDC) + multi-tenant batches.
* Versioned model registry (используется `model_versions` в БД).
* Active retry queue с экспоненциальным back-off (сейчас ручной счётчик
  `attempt`).
* Деплой через Helm chart + S3-совместимое хранилище.
* C++-модуль: skeleton + RANSAC line/circle перенос на C++ через cgo,
  чтобы держать большие чертежи под 1 секунду.

## Долгий горизонт

* Поддержка ГОСТ 2.305 (виды, разрезы, сечения) — связывание видов одной
  детали.
* Constraint solver (Sketchpad-style) поверх обнаруженных constraints.
* Импорт обратно в КОМПАС-3D через KOMPAS-API (только если потребуется
  тестирование round-trip совместимости).

# drawing2dxf

Локальная система преобразования растровых сканов инженерных чертежей в DXF
(совместимый с КОМПАС-3D).

> **Важно.** Это **рабочий production-ready skeleton**, в котором реализован
> весь pipeline `image → preprocessing → geometry
> fitting → CAD JSON → DXF` в **classical / mock-режиме без обученных
> моделей**. Веса YOLO11 / PaddleOCR / Qwen2.5-VL / SAM 2.1 подключаются позже
> через документированные интерфейсы. Mock-классификаторы и эвристики не
> претендуют на production-точность — их задача обеспечить непрерывность
> pipeline и валидную структуру артефактов.

## Что умеет проект сейчас

* Загрузка через web-панель множества файлов одновременно: `PDF`, `PNG`,
  `JPG/JPEG`, `TIFF`, `WEBP`, `ZIP`, `RAR`, `7Z`, `TAR`, `TAR.GZ`, `TAR.BZ2`,
  `TAR.XZ`.
* Безопасное распаковывание архивов (защита от path traversal, symlink,
  абсолютных путей, zip-bomb, лимиты по количеству и размеру файлов).
* Извлечение страниц из PDF (через poppler `pdftoppm` или встроенные
  растровые объекты, если возможно).
* Нормализация: grayscale, denoise, контраст, adaptive threshold, deskew,
  frame crop, оценка качества и DPI.
* Mock OCR + полноценный rule-based **dimension parser** для строк вида
  `Ø40H11`, `R25`, `M12`, `80±0.2`, `1×45°`, `2 отв. Ø10`, `10-0.1` и т.п.
* MVP **geometry restoration**: skeletonization, graph chains, RANSAC LINE,
  RANSAC CIRCLE/ARC, merging collinear segments, snapping углов, обработка
  break symbols.
* **DXF export через ezdxf**: настоящие LINE / ARC / CIRCLE / LWPOLYLINE /
  TEXT, отдельные слои для геометрии / осевых / штриховки / break-символов /
  низкоуверенных примитивов / raster reference. Версия по умолчанию `R2010`,
  fallback `R2000`.
* QA: raster IoU, chamfer, Hausdorff, heatmap, флаг `requires_review`.
* Web UI на React + Vite + TypeScript: upload page, batch dashboard,
  review-страница с overlay (исходник / маски / CAD primitives / OCR / QA
  heatmap), export-страница.
* PostgreSQL для metadata, MinIO для бинарных артефактов, Redpanda как
  Kafka-broker, единый event envelope, idempotent workers, retries,
  deadletter.
* Prometheus + Grafana, structured logging, `/healthz` на каждом сервисе.

## Что **НЕ** делает проект (по требованиям)

* Не обучает модели.
* Не скачивает веса автоматически.
* Не вызывает облачные API.
* Не претендует, что mock-инференс эквивалентен обученным моделям.
* Не экспортирует спецификации, ведомости и таблицы спецификаций в DXF.

## Целевая платформа

* Ubuntu Server 22.04 / 24.04.
* Docker + Docker Compose.
* GPU: опционально, оптимально — NVIDIA RTX 4090 24GB (см.
  `docker-compose.gpu.yml`). Без GPU всё работает в CPU/mock-режиме.
* RAM target: 128 GB, минимум 64 GB.
* CPU: 16+ ядер.
* NVMe 2 TB+ под активные batch.

## Быстрый старт

```bash
cp .env.example .env
make up
make migrate-up
make create-bucket
make run-sample
```

Открыть [http://localhost:5173](http://localhost:5173) — web-панель.
API доступен на `http://localhost:8080`.

## Структура репозитория

```
drawing2dxf/
  apps/
    web/                       — React + Vite + TS web UI
    api/                       — Go REST + WebSocket/SSE API
  workers-go/
    ingest-worker/             — приём файлов, распаковка архивов, извлечение страниц
    export-packager/           — упаковка результатов batch в ZIP
  services-python/
    common/                    — общая Python-библиотека (kafka, storage, схемы)
    preprocess-service/        — denoise / deskew / threshold / quality
    ocr-service/               — mock OCR + dimension parser (PP-OCRv5 iface)
    geometry-service/          — skeleton → LINE/ARC/CIRCLE → CAD JSON
    qa-service/                — raster IoU / chamfer / hausdorff / heatmap
    dxf-export-service/        — CAD JSON → DXF через ezdxf
    vlm-review-service/        — placeholder под Qwen2.5-VL
    sam-assist-service/        — placeholder под SAM 2.1
  packages/
    schemas/                   — JSON Schema для CAD JSON, OpenAPI
  infra/                       — postgres init, prometheus, nginx
  docs/                        — архитектура, контракты моделей, dev-план
  tests/                       — unit + integration + e2e fixtures
  scripts/                     — dev seeding, run_local_pipeline.sh
```

## Подробнее

* [docs/architecture.md](docs/architecture.md) — общая архитектура и схема.
* [docs/cad_json.md](docs/cad_json.md) — формат CAD JSON.
* [docs/dxf_layers.md](docs/dxf_layers.md) — слои и стиль DXF под КОМПАС-3D.
* [docs/model_contracts.md](docs/model_contracts.md) — что и как подключать
  как обученные модели.
* [docs/development_plan.md](docs/development_plan.md) — план дальнейшего
  развития.

## Лицензия

Внутренний инженерный проект. Лицензия — по договорённости.

# Контракты ML-моделей

Этот документ — единственная точка, где описано, **какие модели будут
подключены позже** и **как сделать это без переписывания pipeline**.

> Принципиальное ограничение: проект не скачивает веса автоматически и не
> вызывает облачные API. Все модели запускаются локально, на машине
> пользователя. До поставки весов соответствующий сервис работает в
> classical/mock-режиме.

## 1. YOLO11s-cls — page router

* **Сервис**: `services-python/model-router-service`
* **Контракт**: `app/page_router.py::PageRouter`
* **Реализации**:
  * `app/mock_router.py::MockRouter` — rule-based, активна по умолчанию.
  * `app/yolo_router_interface.py::YoloRouter` — placeholder, активируется
    при `ROUTER_IMPL=yolo` и наличии файла по пути `MODEL_ROUTER_WEIGHTS`.
* **Классы**:
  * `detail_drawing`
  * `assembly_drawing`
  * `specification_sheet`
  * `bad_scan`
  * `unknown`
* **Что делать после получения весов**:
  1. Положить `weights.pt` по пути `${MODEL_ROUTER_WEIGHTS}`
     (default `/models/yolo11s-cls/weights.pt`).
  2. `pip install ultralytics` в Dockerfile (опционально вынесем в GPU image).
  3. `ROUTER_IMPL=yolo`.
  4. Restart.

## 2. YOLO11m-seg — drawing segmenter

* **Сервис**: `services-python/segmentation-service`
* **Контракт**: `app/yolo11_segmenter_interface.py::Yolo11Segmenter`
* **Fallback**: `app/mock_segmenter.py::MockSegmenter` (classical CV).
* **Классы (id → name)**:
  ```
  0  visible_geometry
  1  hidden_geometry
  2  centerline
  3  dimension_graphics
  4  text
  5  hatch
  6  break_symbol
  7  frame_titleblock
  8  stamp_signature
  9  noise
  ```
* Реализация tile-инференса вынесена в TODO внутри
  `yolo11_segmenter_interface.py`. Геометрический сервис уже умеет читать
  любые маски из MinIO, поэтому замена backend-а не требует изменений
  downstream.

## 3. PaddleOCR PP-OCRv5 — OCR

* **Сервис**: `services-python/ocr-service`
* **Контракт**: `app/paddleocr_interface.py::PaddleOCRBackend`
* **Fallback**: `app/mock_ocr.py::MockOCR`.
* **Output schema** (соответствует `cadjson.schema.json`):
  ```json
  {
    "id": "uuid",
    "text": "Ø40H11",
    "bbox_px": [x1, y1, x2, y2],
    "rotation_deg": 0,
    "confidence": 0.91,
    "kind": "dimension_text|technical_text|titleblock_text|unknown",
    "parsed": { ... }
  }
  ```
* **Dimension parser** (`app/dimension_parser.py`) работает независимо от
  выбранного backend и корректно разбирает основные русские/английские
  обозначения (см. unit-tests).

## 4. Qwen2.5-VL — review helper

* **Сервис**: `services-python/vlm-review-service`
* **Контракт**: `app/qwen25vl_interface.py::QwenVLM`
* **Роль**: вспомогательный пересмотр. **Никогда** не источник CAD-истины.
* **Fallback**: `app/mock_vlm.py::MockVLM` отвечает примитивной диагностикой.

## 5. SAM 2.1 — interactive mask assistant

* **Сервис**: `services-python/sam-assist-service`
* **Контракт**: `app/sam21_interface.py::SAM21`
* **Роль**: ручное докрашивание масок reviewer-ом в web-UI. **Не**
  автоматический CAD-генератор.
* **Fallback**: `app/mock_sam.py::MockSAM`.

## Общее правило подключения

Каждый сервис при старте проверяет:

1. `XXX_IMPL=` явно указан в env;
2. Существует файл/директория с весами;
3. Опциональные ML-зависимости установлены.

Если что-то отсутствует — сервис **тёплоидно** деградирует в mock и
логирует причину в JSON-формате (`structlog`).

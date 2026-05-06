# DXF слои и стиль для КОМПАС-3D

dxf-export-service создаёт DXF (R2010 по умолчанию, R2000 fallback) с
заранее объявленным набором слоёв, согласованным с типичными настройками
КОМПАС-3D:

| Layer name              | ACI color | Role           | Linetype    | Что туда попадает                                    |
|-------------------------|-----------|----------------|-------------|------------------------------------------------------|
| `00_FRAME`              | 8 grey    | frame          | CONTINUOUS  | Внешняя рамка чертежа.                               |
| `01_TITLE_BLOCK`        | 8 grey    | titleblock     | CONTINUOUS  | Штамп / основная надпись.                            |
| `02_PART_VISIBLE`       | 7 white   | geometry       | CONTINUOUS  | **Видимая геометрия детали (LINE/ARC/CIRCLE).**      |
| `03_PART_HIDDEN`        | 5 blue    | hidden         | DASHED      | Невидимые контуры. Сейчас пуст в classical-режиме.   |
| `04_CENTER_AXIS`        | 1 red     | centerline     | CENTER      | Осевые / центровые линии.                            |
| `05_DIM_LINES`          | 3 green   | dimension      | CONTINUOUS  | Размерная графика (выноски, стрелки, размерные линии). |
| `06_DIM_TEXT`           | 3 green   | dimension_text | CONTINUOUS  | Текст размеров (`Ø40H11`, `R25` и т.п.).            |
| `07_TEXT_NOTES`         | 7 white   | text           | CONTINUOUS  | Технические требования и прочий текст.              |
| `08_HATCH`              | 2 yellow  | hatch          | CONTINUOUS  | Штриховка сечений.                                   |
| `09_BREAK_SYMBOLS`      | 4 cyan    | break_symbol   | CONTINUOUS  | Символы разрыва длинных деталей.                    |
| `10_TABLES_ON_DRAWING`  | 8 grey    | tables         | CONTINUOUS  | Таблицы прямо на чертеже (НЕ спецификации).         |
| `90_QA_LOW_CONFIDENCE`  | 6 magenta | qa             | CONTINUOUS  | Низкоуверенные примитивы. Reviewer аудитирует.       |
| `99_RASTER_REFERENCE`   | 9 grey    | raster         | CONTINUOUS  | (Опционально) raster-фон для визуальной сверки.     |

## Сущности

| CAD JSON `type` | DXF entity     | Метод ezdxf            |
|-----------------|----------------|-------------------------|
| `LINE`          | LINE           | `msp.add_line`         |
| `CIRCLE`        | CIRCLE         | `msp.add_circle`       |
| `ARC`           | ARC            | `msp.add_arc`          |
| `LWPOLYLINE`    | LWPOLYLINE     | `msp.add_lwpolyline`   |
| `TEXT`          | TEXT           | `msp.add_text`         |

В первой версии **размеры экспортируются как набор LINE + TEXT**, не как
полноценные DIMENSION-сущности. Это сознательное упрощение для совместимости
с КОМПАС: native DIMENSION требует точно настроенных DIMSTYLE, что мы
оставляем как future work.

## Координаты и единицы

* Pixel coordinates → millimetres через `document.px_per_mm`. Если
  `px_per_mm` не задан, считаем `1 px = 1 mm`.
* Y-axis flip: DXF Y растёт вверх, raster Y — вниз. Конвертация:
  `y_mm = (page_height_px - y_px) / px_per_mm`.
* Угол ARC при отражении Y инвертируется: `(start, end) → (-end, -start)
  mod 360`.

## Что **не** экспортируется

* Спецификации, ведомости, BOM-таблицы — они отбрасываются router'ом.
* Рамки и штамп НЕ помещаются в `02_PART_VISIBLE` (только на `00_FRAME` /
  `01_TITLE_BLOCK`).
* Шум (`noise`) и `frame_titleblock` пиксели не порождают примитивы.

/** Helpers shared by the Konva-based review canvas. */

export type Primitive = {
  id: string;
  type: "LINE" | "ARC" | "CIRCLE" | "LWPOLYLINE" | "TEXT";
  layer: string;
  confidence?: number;
  p1?: [number, number];
  p2?: [number, number];
  center?: [number, number];
  radius?: number;
  start_angle_deg?: number;
  end_angle_deg?: number;
  vertices?: [number, number][];
  closed?: boolean;
  text?: string;
  position?: [number, number];
};

export type CADJSON = {
  schema_version: string;
  document: {
    page_id: string;
    units: string;
    image_size_px?: [number, number];
    page_type?: string;
  };
  layers: { name: string; role: string; color?: number }[];
  primitives: Primitive[];
  ocr?: {
    id: string;
    text: string;
    bbox_px: [number, number, number, number];
    rotation_deg?: number;
    confidence?: number;
    kind?: string;
  }[];
  qa?: {
    requires_review?: boolean;
    warnings?: string[];
    raster_iou?: number;
    chamfer_px?: number;
  };
};

export const LAYER_COLORS: Record<string, string> = {
  "00_FRAME": "#888",
  "01_TITLE_BLOCK": "#888",
  "02_PART_VISIBLE": "#e6edf3",
  "03_PART_HIDDEN": "#a371f7",
  "04_CENTER_AXIS": "#f85149",
  "05_DIM_LINES": "#56d364",
  "06_DIM_TEXT": "#56d364",
  "07_TEXT_NOTES": "#e6edf3",
  "08_HATCH": "#e3b341",
  "09_BREAK_SYMBOLS": "#ffa657",
  "10_TABLES_ON_DRAWING": "#888",
  "90_QA_LOW_CONFIDENCE": "#ff7eb6",
  "99_RASTER_REFERENCE": "#444",
};

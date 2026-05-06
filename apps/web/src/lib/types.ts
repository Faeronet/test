export type Batch = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type FileRow = {
  id: string;
  batch_id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  storage_uri: string;
  status: string;
};

export type Page = {
  id: string;
  batch_id: string;
  file_id: string;
  page_index: number;
  page_type: string;
  status: string;
  width_px?: number;
  height_px?: number;
  dpi?: number;
  raw_image_uri?: string;
  normalized_image_uri?: string;
  preview_uri?: string;
  skip_reason?: string;
  confidence?: number;
};

export type BatchDetail = Batch & {
  files?: FileRow[];
  pages?: Page[];
};

export type Artifact = {
  id: string;
  batch_id: string;
  page_id?: string;
  kind: string;
  uri: string;
  mime_type: string;
  metadata?: Record<string, unknown> & { presigned_url?: string };
  created_at: string;
};

export type QAMetrics = {
  id?: string;
  page_id?: string;
  raster_iou?: number;
  chamfer_px?: number;
  hausdorff_px?: number;
  requires_review?: boolean;
  warnings?: string[];
};

export type EventEnvelope = {
  event_id: string;
  event_type: string;
  batch_id?: string;
  file_id?: string;
  page_id?: string;
  artifact_uri?: string;
  attempt: number;
  created_at: string;
  payload?: Record<string, unknown>;
};

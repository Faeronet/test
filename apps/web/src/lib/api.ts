import type { Artifact, Batch, BatchDetail, Page, QAMetrics } from "./types";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8080";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  if (resp.status === 204) return undefined as unknown as T;
  return (await resp.json()) as T;
}

export const api = {
  baseUrl: BASE_URL,

  createBatch: (name: string) =>
    request<Batch>("/api/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),

  listBatches: () => request<Batch[]>("/api/batches"),

  getBatch: (id: string) => request<BatchDetail>(`/api/batches/${id}`),

  uploadFiles: async (batchId: string, files: File[]) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    const resp = await fetch(`${BASE_URL}/api/batches/${batchId}/upload`, {
      method: "POST",
      body: fd,
    });
    if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
    return (await resp.json()) as { files: { id: string; original_name: string }[] };
  },

  getPage: (id: string) => request<Page>(`/api/pages/${id}`),
  getArtifacts: (id: string) => request<Artifact[]>(`/api/pages/${id}/artifacts`),
  getCadJSON: (id: string) => request<unknown>(`/api/pages/${id}/cadjson`),
  getQA: (id: string) => request<QAMetrics>(`/api/pages/${id}/qa`),

  acceptReview: (id: string) =>
    request(`/api/pages/${id}/review/accept`, { method: "POST" }),

  reprocess: (id: string) =>
    request(`/api/pages/${id}/reprocess`, { method: "POST" }),

  requestExport: (batchId: string, format: "zip" | "dxf" = "zip") =>
    request<{ id: string; status: string }>(`/api/batches/${batchId}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ format }),
    }),

  exportDownloadUrl: (exportId: string) =>
    `${BASE_URL}/api/exports/${exportId}/download`,
};

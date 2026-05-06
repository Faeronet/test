import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { BatchDetail } from "../lib/types";
import { useEventStream } from "../lib/websocket";
import BatchDashboard from "../components/BatchDashboard/BatchDashboard";
import ExportPanel from "../components/ExportPanel/ExportPanel";

type Filter = "all" | "drawings" | "specs" | "review" | "exported" | "failed";

export default function BatchPage() {
  const { batchId = "" } = useParams();
  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const events = useEventStream(batchId);

  useEffect(() => {
    if (!batchId) return;
    api.getBatch(batchId).then(setBatch).catch(() => setBatch(null));
  }, [batchId]);

  // Re-fetch the batch a few times when relevant events arrive.
  useEffect(() => {
    const last = events[events.length - 1];
    if (!last || !batchId) return;
    const t = setTimeout(() => {
      api.getBatch(batchId).then(setBatch).catch(() => undefined);
    }, 600);
    return () => clearTimeout(t);
  }, [events, batchId]);

  if (!batch) {
    return (
      <div className="page">
        <p className="muted">Загрузка партии…</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h2 style={{ marginTop: 0 }}>{batch.name}</h2>
      <p className="muted">
        статус: {batch.status}, файлов: {batch.files?.length ?? 0}, страниц:{" "}
        {batch.pages?.length ?? 0}
      </p>
      <ExportPanel batchId={batch.id} />
      <div className="card">
        <BatchDashboard batch={batch} filter={filter} onFilter={setFilter} />
      </div>
      <details className="card">
        <summary className="muted">Поток событий ({events.length})</summary>
        <pre style={{ maxHeight: 240, overflow: "auto", fontSize: 11 }}>
          {events
            .slice(-50)
            .map((e) => `${e.created_at}  ${e.event_type}  page=${e.page_id ?? "-"}`)
            .join("\n")}
        </pre>
      </details>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Artifact, Page, QAMetrics } from "../lib/types";
import type { CADJSON } from "../lib/canvas";
import DrawingViewer from "../components/DrawingViewer/DrawingViewer";
import QaPanel from "../components/QaPanel/QaPanel";

const ALL_LAYERS = [
  "02_PART_VISIBLE",
  "03_PART_HIDDEN",
  "04_CENTER_AXIS",
  "05_DIM_LINES",
  "06_DIM_TEXT",
  "07_TEXT_NOTES",
  "08_HATCH",
  "09_BREAK_SYMBOLS",
  "90_QA_LOW_CONFIDENCE",
];

export default function ReviewPage() {
  const { pageId = "" } = useParams();
  const [page, setPage] = useState<Page | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [cad, setCad] = useState<CADJSON | null>(null);
  const [qa, setQa] = useState<QAMetrics | undefined>();
  const [layers, setLayers] = useState<Set<string>>(new Set(ALL_LAYERS));
  const [showOcr, setShowOcr] = useState(true);

  useEffect(() => {
    if (!pageId) return;
    api.getPage(pageId).then(setPage).catch(() => setPage(null));
    api.getArtifacts(pageId).then(setArtifacts).catch(() => setArtifacts([]));
    api.getCadJSON(pageId).then((d) => setCad(d as CADJSON)).catch(() => setCad(null));
    api.getQA(pageId).then(setQa).catch(() => setQa(undefined));
  }, [pageId]);

  const previewUrl = useMemo(() => {
    const a = artifacts.find(
      (x) => x.kind === "preview" || x.kind === "normalized" || x.kind === "raw",
    );
    return a?.metadata?.presigned_url as string | undefined;
  }, [artifacts]);

  const heatmapUrl = useMemo(() => {
    const a = artifacts.find((x) => x.kind === "qa_heatmap");
    return a?.metadata?.presigned_url as string | undefined;
  }, [artifacts]);

  const toggle = (layer: string) => {
    setLayers((prev) => {
      const next = new Set(prev);
      next.has(layer) ? next.delete(layer) : next.add(layer);
      return next;
    });
  };

  if (!page) {
    return (
      <div className="page">
        <p className="muted">Загрузка страницы…</p>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: "100%" }}>
      <div className="review-grid">
        <div>
          <div className="toolbar">
            {ALL_LAYERS.map((l) => (
              <button
                key={l}
                className={`layer-toggle ${layers.has(l) ? "active" : ""}`}
                onClick={() => toggle(l)}
              >
                {l}
              </button>
            ))}
            <button
              className={`layer-toggle ${showOcr ? "active" : ""}`}
              onClick={() => setShowOcr((v) => !v)}
            >
              OCR
            </button>
          </div>
          <DrawingViewer
            imageSrc={previewUrl}
            cad={cad}
            visibleLayers={layers}
            showOcr={showOcr}
          />
        </div>
        <aside className="side-panel">
          <div className="kv">
            <span className="k">page_id</span><span style={{ wordBreak: "break-all" }}>{page.id}</span>
            <span className="k">type</span><span>{page.page_type}</span>
            <span className="k">status</span><span>{page.status}</span>
            <span className="k">confidence</span>
            <span>{page.confidence != null ? page.confidence.toFixed(2) : "—"}</span>
            <span className="k">size</span>
            <span>{page.width_px}×{page.height_px}px @ {page.dpi ?? "?"} dpi</span>
          </div>

          <QaPanel qa={qa} heatmapUrl={heatmapUrl} />

          <h3 style={{ fontSize: 14, marginTop: 16 }}>Действия</h3>
          <div className="flex" style={{ flexWrap: "wrap" }}>
            <button className="btn" onClick={() => api.acceptReview(page.id).then(() => api.getPage(page.id).then(setPage))}>
              Принять
            </button>
            <button className="btn secondary" onClick={() => api.reprocess(page.id)}>
              Повторно обработать
            </button>
          </div>

          <h3 style={{ fontSize: 14, marginTop: 16 }}>Артефакты</h3>
          <table className="simple">
            <thead>
              <tr><th>kind</th><th>uri</th></tr>
            </thead>
            <tbody>
              {artifacts.map((a) => (
                <tr key={a.id}>
                  <td>{a.kind}</td>
                  <td>
                    {a.metadata?.presigned_url ? (
                      <a href={a.metadata.presigned_url as string} target="_blank" rel="noreferrer">
                        download
                      </a>
                    ) : (
                      <span className="muted">{a.uri}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </aside>
      </div>
    </div>
  );
}

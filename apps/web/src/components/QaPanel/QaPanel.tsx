import type { QAMetrics } from "../../lib/types";

type Props = { qa?: QAMetrics; heatmapUrl?: string };

export default function QaPanel({ qa, heatmapUrl }: Props) {
  if (!qa) {
    return <p className="muted">QA не запускался.</p>;
  }
  return (
    <div>
      <h3 style={{ margin: "0 0 8px 0", fontSize: 14 }}>QA</h3>
      <div className="kv">
        <span className="k">raster IoU</span>
        <span>{fmt(qa.raster_iou)}</span>
        <span className="k">chamfer</span>
        <span>{fmtPx(qa.chamfer_px)}</span>
        <span className="k">hausdorff</span>
        <span>{fmtPx(qa.hausdorff_px)}</span>
        <span className="k">requires review</span>
        <span>{qa.requires_review ? "yes" : "no"}</span>
      </div>
      {(qa.warnings ?? []).length > 0 ? (
        <ul className="warnings" style={{ paddingLeft: 16 }}>
          {qa.warnings!.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      {heatmapUrl ? (
        <img src={heatmapUrl} alt="QA heatmap" style={{ width: "100%", marginTop: 8, borderRadius: 4 }} />
      ) : null}
    </div>
  );
}

const fmt = (v?: number) => (v == null ? "—" : v.toFixed(3));
const fmtPx = (v?: number) =>
  v == null || !Number.isFinite(v) ? "—" : `${v.toFixed(2)} px`;

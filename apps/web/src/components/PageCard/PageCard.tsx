import { Link } from "react-router-dom";
import type { Page } from "../../lib/types";

const TYPE_LABEL: Record<string, string> = {
  detail_drawing: "Деталь",
  assembly_drawing: "Сборка",
  specification_sheet: "Спецификация",
  bad_scan: "Плохой скан",
  unknown: "—",
};

export default function PageCard({ page }: { page: Page }) {
  const isSkipped =
    page.status === "skipped" || page.page_type === "specification_sheet";
  return (
    <div className="page-card">
      <div className="flex" style={{ marginBottom: 6 }}>
        <span className={`status ${normaliseStatus(page.status)}`}>
          {page.status}
        </span>
        <span className="muted">#{page.page_index}</span>
      </div>
      <div style={{ fontSize: 14, marginBottom: 4 }}>
        {TYPE_LABEL[page.page_type] ?? page.page_type}
      </div>
      <div className="muted" style={{ fontSize: 12 }}>
        {page.confidence != null
          ? `confidence ${(page.confidence * 100).toFixed(0)}%`
          : "no confidence yet"}
      </div>
      {page.skip_reason ? (
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
          skip: {page.skip_reason}
        </div>
      ) : null}
      <div style={{ marginTop: 10 }}>
        {!isSkipped ? (
          <Link to={`/pages/${page.id}/review`}>Review →</Link>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>
            (исключено из CAD)
          </span>
        )}
      </div>
    </div>
  );
}

function normaliseStatus(s: string): string {
  return s.replace(/[^a-z_]/gi, "_").toLowerCase();
}

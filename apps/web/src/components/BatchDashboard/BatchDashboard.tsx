import type { BatchDetail } from "../../lib/types";
import PageCard from "../PageCard/PageCard";

const FILTERS = [
  { id: "all", label: "Все" },
  { id: "drawings", label: "Чертежи" },
  { id: "specs", label: "Спецификации" },
  { id: "review", label: "На проверку" },
  { id: "exported", label: "Экспортировано" },
  { id: "failed", label: "Ошибки" },
] as const;

type Filter = (typeof FILTERS)[number]["id"];

type Props = {
  batch: BatchDetail;
  filter: Filter;
  onFilter: (f: Filter) => void;
};

export default function BatchDashboard({ batch, filter, onFilter }: Props) {
  const pages = batch.pages ?? [];
  const filtered = pages.filter((p) => {
    switch (filter) {
      case "drawings":
        return p.page_type === "detail_drawing" || p.page_type === "assembly_drawing";
      case "specs":
        return p.page_type === "specification_sheet" || p.status === "skipped";
      case "review":
        return p.status === "review_required";
      case "exported":
        return p.status === "exported";
      case "failed":
        return p.status === "failed";
      default:
        return true;
    }
  });
  return (
    <>
      <div className="toolbar">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            className={`layer-toggle ${filter === f.id ? "active" : ""}`}
            onClick={() => onFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="batch-grid">
        {filtered.map((p) => (
          <PageCard key={p.id} page={p} />
        ))}
        {filtered.length === 0 ? (
          <p className="muted">Нет страниц по фильтру.</p>
        ) : null}
      </div>
    </>
  );
}

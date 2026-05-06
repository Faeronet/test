import { useParams } from "react-router-dom";
import ExportPanel from "../components/ExportPanel/ExportPanel";

export default function ExportPage() {
  const { batchId = "" } = useParams();
  return (
    <div className="page">
      <h2>Экспорт</h2>
      <ExportPanel batchId={batchId} />
      <p className="muted">
        Экспорт собирает DXF по всем не-спецификационным страницам пакета и упаковывает их в ZIP.
      </p>
    </div>
  );
}

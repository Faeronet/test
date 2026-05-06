import { useState } from "react";
import { api } from "../../lib/api";

type Props = { batchId: string };

export default function ExportPanel({ batchId }: Props) {
  const [busy, setBusy] = useState(false);
  const [exportId, setExportId] = useState<string | null>(null);

  const onExport = async () => {
    setBusy(true);
    try {
      const r = await api.requestExport(batchId, "zip");
      setExportId(r.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="flex">
        <button className="btn" onClick={onExport} disabled={busy}>
          {busy ? "Экспортирую…" : "Экспорт DXF (ZIP)"}
        </button>
        {exportId ? (
          <a className="btn secondary" href={api.exportDownloadUrl(exportId)}>
            Скачать batch.zip
          </a>
        ) : null}
      </div>
      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        Спецификации и пропущенные страницы в DXF не попадают.
      </p>
    </div>
  );
}

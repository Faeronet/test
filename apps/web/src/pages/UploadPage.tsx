import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import UploadDropzone from "../components/UploadDropzone/UploadDropzone";

export default function UploadPage() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onFiles = async (files: File[]) => {
    setError(null);
    try {
      const batch = await api.createBatch(name || `batch-${new Date().toISOString().slice(0, 19)}`);
      await api.uploadFiles(batch.id, files);
      nav(`/batches/${batch.id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Новая партия</h2>
        <p className="muted">
          Загрузите PDF, изображения или архивы. Спецификации классифицируются автоматически
          и в DXF не экспортируются. Чертежи проходят полный pipeline:
          preprocessing → segmentation → OCR → geometry → DXF.
        </p>
        <div className="flex" style={{ marginBottom: 12 }}>
          <input
            placeholder="Имя партии (опционально)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{
              flex: 1,
              background: "#0d1117",
              border: "1px solid #30363d",
              color: "#e6edf3",
              padding: "8px 12px",
              borderRadius: 6,
            }}
          />
        </div>
        <UploadDropzone onFiles={onFiles} />
        {error ? <p style={{ color: "#f85149" }}>{error}</p> : null}
      </div>
    </div>
  );
}

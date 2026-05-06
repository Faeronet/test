import { useCallback, useState } from "react";

type Props = {
  onFiles: (files: File[]) => void | Promise<void>;
  disabled?: boolean;
  accept?: string;
};

const DEFAULT_ACCEPT =
  ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.bmp,.zip,.rar,.7z,.tar,.gz,.bz2,.xz,.tgz,.tbz2,.txz";

export default function UploadDropzone({ onFiles, disabled, accept = DEFAULT_ACCEPT }: Props) {
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);

  const handle = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      setBusy(true);
      try {
        await onFiles(Array.from(files));
      } finally {
        setBusy(false);
      }
    },
    [onFiles],
  );

  return (
    <label
      className={`dropzone ${over ? "over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={async (e) => {
        e.preventDefault();
        setOver(false);
        if (disabled) return;
        await handle(e.dataTransfer.files);
      }}
    >
      <input
        type="file"
        multiple
        accept={accept}
        disabled={disabled || busy}
        onChange={(e) => handle(e.target.files)}
      />
      <p style={{ margin: 0, fontSize: 16 }}>
        {busy
          ? "Uploading…"
          : "Drag & drop PDF / images / archives here, or click to choose"}
      </p>
      <p style={{ marginTop: 8, fontSize: 12 }} className="muted">
        Accepted: PDF, PNG, JPG, TIFF, WEBP, ZIP, RAR, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ
      </p>
    </label>
  );
}

import { useRef, useState } from "react";
import { useUploadInvoices } from "../hooks/useUploadInvoices";
import { ApiError } from "../api/client";
import { UploadIcon } from "./icons";

const ACCEPTED_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp";

export function UploadButton() {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadInvoices();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex flex-col items-end gap-1.5">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
        onChange={(event) => {
          const files = event.target.files;
          if (files && files.length > 0) {
            setError(null);
            upload.mutate(files, {
              onError: (err) => setError(err instanceof ApiError ? err.message : "Nahrání se nezdařilo."),
            });
          }
          event.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={upload.isPending}
        onClick={() => inputRef.current?.click()}
        className="flex items-center gap-2 rounded-[10px] bg-accent px-4 py-2.5 text-[13.5px] font-semibold text-accent-ink shadow-[var(--shadow-panel)] transition-transform hover:-translate-y-px disabled:opacity-60"
      >
        <UploadIcon className="h-4 w-4" />
        {upload.isPending ? "Nahrávám…" : "Nahrát faktury"}
      </button>
      {error && <p className="max-w-xs text-right text-[12px] text-bad">{error}</p>}
    </div>
  );
}

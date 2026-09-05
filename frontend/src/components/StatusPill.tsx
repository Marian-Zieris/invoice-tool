import type { InvoiceStatus } from "../api/types";

const STATUS_CONFIG: Record<InvoiceStatus, { label: string; className: string; pulse?: boolean }> = {
  uploaded: { label: "Nahráno", className: "bg-busy-soft text-busy" },
  processing: { label: "Zpracovává se", className: "bg-busy-soft text-busy", pulse: true },
  needs_review: { label: "Ke kontrole", className: "bg-warn-soft text-warn" },
  reviewed: { label: "Zkontrolováno", className: "bg-good-soft text-good" },
  exported: { label: "Exportováno", className: "bg-good-soft text-good" },
  ocr_failed: { label: "Chyba OCR", className: "bg-bad-soft text-bad" },
  extraction_failed: { label: "Chyba extrakce", className: "bg-bad-soft text-bad" },
};

export function StatusPill({ status }: { status: InvoiceStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold ${config.className}`}
    >
      <span className={`h-[5px] w-[5px] rounded-full bg-current ${config.pulse ? "animate-pulse-dot" : ""}`} />
      {config.label}
    </span>
  );
}

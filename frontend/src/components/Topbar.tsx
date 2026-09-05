import type { InvoiceSummary } from "../api/types";
import { UploadButton } from "./UploadButton";
import { ThemeToggle } from "./ThemeToggle";

function summarize(invoices: InvoiceSummary[] | undefined): string {
  if (!invoices) return "Načítám…";
  if (invoices.length === 0) return "Zatím žádné doklady";
  const needsReview = invoices.filter((invoice) => invoice.status === "needs_review").length;
  const docsWord = invoices.length === 1 ? "doklad" : invoices.length < 5 ? "doklady" : "dokladů";
  const base = `${invoices.length} ${docsWord}`;
  if (needsReview === 0) return base;
  return `${base} · ${needsReview} čeká na kontrolu`;
}

export function Topbar({ invoices }: { invoices: InvoiceSummary[] | undefined }) {
  return (
    <header className="flex items-center justify-between border-b border-border px-8 py-5">
      <div>
        <h1 className="m-0 text-[19px] font-bold tracking-tight text-ink" style={{ textWrap: "balance" }}>
          Faktury
        </h1>
        <p className="mt-0.5 text-[13px] text-ink-muted">{summarize(invoices)}</p>
      </div>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <UploadButton />
      </div>
    </header>
  );
}

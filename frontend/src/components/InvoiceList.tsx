import { useState } from "react";
import type { InvoiceSummary } from "../api/types";
import { formatAmount, formatDate, formatDateTime } from "../lib/format";
import { useDeleteInvoice } from "../hooks/useDeleteInvoice";
import { useMergeInvoices } from "../hooks/useMergeInvoices";
import { ApiError } from "../api/client";
import { StatusPill } from "./StatusPill";
import { CheckIcon, CloseIcon, ExportIcon, MergeIcon, TrashIcon } from "./icons";

interface InvoiceListProps {
  invoices: InvoiceSummary[];
  isLoading: boolean;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDeleted: (id: number) => void;
  onMerged: (newInvoiceId: number) => void;
  selectedForExport: Set<number>;
  onToggleExport: (id: number) => void;
  onToggleAll: () => void;
  onExport: () => void;
  isExporting: boolean;
}

function listDate(invoice: InvoiceSummary): string {
  return invoice.invoice_date ? formatDate(invoice.invoice_date) : formatDateTime(invoice.created_at);
}

export function InvoiceList({
  invoices,
  isLoading,
  selectedId,
  onSelect,
  onDeleted,
  onMerged,
  selectedForExport,
  onToggleExport,
  onToggleAll,
  onExport,
  isExporting,
}: InvoiceListProps) {
  const allSelected = invoices.length > 0 && selectedForExport.size === invoices.length;
  const deleteInvoice = useDeleteInvoice();
  const mergeInvoices = useMergeInvoices();
  const [mergeError, setMergeError] = useState<string | null>(null);
  // Vlastní potvrzení místo window.confirm() - nativní dialog se v některých
  // prohlížečích/rozšířeních chová nespolehlivě (tiše se potlačí a rovnou
  // vrátí false, takže klik na koš vypadá, že "nic nedělá").
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function handleMerge() {
    setMergeError(null);
    mergeInvoices.mutate(Array.from(selectedForExport), {
      onSuccess: (merged) => onMerged(merged.id),
      onError: (err) => setMergeError(err instanceof ApiError ? err.message : "Sloučení se nezdařilo."),
    });
  }

  return (
    <section className="flex min-h-0 flex-col border-r border-border md:w-[360px] md:flex-none">
      <div className="flex flex-col gap-2.5 px-5 pb-3 pt-4">
        <label className="flex cursor-pointer items-center gap-1.5 text-[12.5px] text-ink-muted">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onToggleAll}
            disabled={invoices.length === 0}
            className="accent-accent"
          />
          Vybrat vše
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={selectedForExport.size < 2 || mergeInvoices.isPending}
            onClick={handleMerge}
            title="Sloučí vybrané faktury do jedné nové - původní zůstanou zachované"
            className="flex items-center gap-1.5 rounded-[10px] border border-border bg-surface px-3 py-2 text-[13px] font-semibold text-ink transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface"
          >
            <MergeIcon className="h-4 w-4" />
            {mergeInvoices.isPending ? "Slučuji…" : `Sloučit (${selectedForExport.size})`}
          </button>
          <button
            type="button"
            disabled={selectedForExport.size === 0 || isExporting}
            onClick={onExport}
            className="flex items-center gap-1.5 rounded-[10px] border border-border bg-surface px-3 py-2 text-[13px] font-semibold text-ink transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface"
          >
            <ExportIcon className="h-4 w-4" />
            {isExporting ? "Exportuji…" : `Exportovat (${selectedForExport.size})`}
          </button>
        </div>
        {mergeError && <p className="text-[12px] text-bad">{mergeError}</p>}
        {deleteError && <p className="text-[12px] text-bad">{deleteError}</p>}
      </div>

      <div className="flex flex-col gap-1.5 overflow-y-auto px-3 pb-4">
        {isLoading && <p className="px-3 py-6 text-center text-[13px] text-ink-muted">Načítám faktury…</p>}

        {!isLoading && invoices.length === 0 && (
          <p className="px-3 py-6 text-center text-[13px] text-ink-muted">
            Zatím žádné faktury. Nahraj první doklad tlačítkem výše.
          </p>
        )}

        {invoices.map((invoice) => {
          const isActive = invoice.id === selectedId;
          return (
            <div
              key={invoice.id}
              onClick={() => {
                setConfirmingDeleteId(null);
                onSelect(invoice.id);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelect(invoice.id);
              }}
              className={`glass-panel group flex cursor-pointer items-start gap-2.5 rounded-[16px] p-3 transition-colors ${
                isActive ? "border-accent bg-accent-soft" : "hover:border-border-strong"
              }`}
            >
              <input
                type="checkbox"
                checked={selectedForExport.has(invoice.id)}
                onClick={(event) => event.stopPropagation()}
                onChange={() => onToggleExport(invoice.id)}
                className="mt-0.5 flex-none accent-accent"
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13.5px] font-semibold text-ink">
                  {invoice.supplier_name ?? "Nerozpoznáno"}
                </div>
                <div className="truncate text-[12px] text-ink-muted">
                  {invoice.original_filename} · {listDate(invoice)}
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <StatusPill status={invoice.status} />
                  <span className="font-mono text-[12.5px] tabular-nums text-ink-muted">
                    {formatAmount(invoice.total_amount, invoice.currency)}
                  </span>
                </div>
              </div>
              {confirmingDeleteId === invoice.id ? (
                <div className="flex flex-none items-center gap-1 self-center" onClick={(event) => event.stopPropagation()}>
                  <span className="text-[11.5px] font-medium text-ink-muted">Smazat?</span>
                  <button
                    type="button"
                    title="Ano, smazat"
                    disabled={deleteInvoice.isPending}
                    onClick={() => {
                      setDeleteError(null);
                      deleteInvoice.mutate(invoice.id, {
                        onSuccess: () => {
                          setConfirmingDeleteId(null);
                          onDeleted(invoice.id);
                        },
                        onError: (err) => setDeleteError(err instanceof ApiError ? err.message : "Smazání se nezdařilo."),
                      });
                    }}
                    className="flex items-center justify-center rounded-[8px] bg-bad-soft p-1.5 text-bad transition-colors hover:brightness-95 disabled:opacity-50"
                  >
                    <CheckIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Zrušit"
                    disabled={deleteInvoice.isPending}
                    onClick={() => setConfirmingDeleteId(null)}
                    className="flex items-center justify-center rounded-[8px] p-1.5 text-ink-muted transition-colors hover:bg-surface-2 disabled:opacity-50"
                  >
                    <CloseIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  title="Smazat fakturu"
                  onClick={(event) => {
                    event.stopPropagation();
                    setConfirmingDeleteId(invoice.id);
                  }}
                  className="flex flex-none items-center justify-center self-center rounded-[8px] p-1.5 text-ink-muted opacity-0 transition-opacity hover:bg-bad-soft hover:text-bad group-hover:opacity-100 disabled:opacity-50"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

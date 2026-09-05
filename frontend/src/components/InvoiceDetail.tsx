import { useState } from "react";
import { useInvoiceDetail } from "../hooks/useInvoiceDetail";
import { useInvoiceItems } from "../hooks/useInvoiceItems";
import { useUpdateItem } from "../hooks/useUpdateItem";
import { useUpdateInvoice } from "../hooks/useUpdateInvoice";
import { useDeleteInvoice } from "../hooks/useDeleteInvoice";
import { formatAmount, formatDate, formatDateTime } from "../lib/format";
import { StatusPill } from "./StatusPill";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { EditableCell } from "./EditableCell";
import { EditIcon, SpinnerIcon, TrashIcon, WarningIcon } from "./icons";

const LOW_CONFIDENCE_THRESHOLD = 0.6;

export function InvoiceDetail({ invoiceId, onDeleted }: { invoiceId: number | null; onDeleted: () => void }) {
  const invoiceQuery = useInvoiceDetail(invoiceId);
  const itemsQuery = useInvoiceItems(invoiceId);
  const updateItem = useUpdateItem();
  const updateInvoice = useUpdateInvoice();
  const deleteInvoice = useDeleteInvoice();
  const [showRawText, setShowRawText] = useState(false);

  if (invoiceId === null) {
    return (
      <section className="flex flex-1 items-center justify-center p-8">
        <p className="text-[14px] text-ink-muted">Vyber fakturu ze seznamu vlevo.</p>
      </section>
    );
  }

  const invoice = invoiceQuery.data;

  if (invoiceQuery.isLoading || !invoice) {
    return (
      <section className="flex flex-1 items-center justify-center p-8">
        <SpinnerIcon className="h-5 w-5 animate-spin text-ink-muted" />
      </section>
    );
  }

  const isPending = invoice.status === "uploaded" || invoice.status === "processing";
  const isFailed = invoice.status === "ocr_failed" || invoice.status === "extraction_failed";
  const items = itemsQuery.data ?? [];

  const lowConfidenceItem = items.find((item) => item.confidence_score < LOW_CONFIDENCE_THRESHOLD);

  return (
    <section className="min-w-0 flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-5">
        <div>
          <h2 className="m-0 mb-1 text-[22px] font-bold tracking-tight text-ink" style={{ textWrap: "balance" }}>
            {invoice.supplier_name ?? "Nerozpoznáno"}
          </h2>
          <div className="flex flex-wrap items-center gap-3.5 text-[13px] text-ink-muted">
            <StatusPill status={invoice.status} />
            <span>{invoice.original_filename}</span>
            <span>{invoice.invoice_date ? formatDate(invoice.invoice_date) : formatDateTime(invoice.created_at)}</span>
          </div>
        </div>
        <div className="flex items-start gap-3">
          {invoice.total_amount !== null && (
            <div className="text-right">
              <div className="font-mono text-[26px] font-semibold tabular-nums text-ink">
                {new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 0 }).format(invoice.total_amount)}
              </div>
              <div className="flex items-center justify-end gap-1 text-[13px] text-ink-muted">
                <span className="w-14">
                  <EditableCell
                    value={invoice.currency}
                    align="right"
                    onSave={(value) => updateInvoice.mutate({ invoiceId: invoice.id, changes: { currency: value.toUpperCase() } })}
                  />
                </span>
                celkem
              </div>
            </div>
          )}
          <button
            type="button"
            title="Smazat fakturu"
            disabled={deleteInvoice.isPending}
            onClick={() => {
              if (window.confirm(`Opravdu smazat fakturu "${invoice.original_filename}"? Tuto akci nelze vrátit zpět.`)) {
                deleteInvoice.mutate(invoice.id, { onSuccess: onDeleted });
              }
            }}
            className="flex flex-none items-center justify-center rounded-[10px] border border-border bg-surface p-2.5 text-ink-muted transition-colors hover:border-bad hover:text-bad disabled:opacity-50"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {isPending && (
        <div className="glass-panel flex items-center gap-3 rounded-[22px] p-6 text-[13.5px] text-ink-muted">
          <SpinnerIcon className="h-5 w-5 flex-none animate-spin" />
          Zpracovává se — OCR a extrakce dat obvykle trvají do minuty. Stránka se sama aktualizuje.
        </div>
      )}

      {isFailed && (
        <div className="glass-panel rounded-[22px] p-6">
          <div className="flex items-start gap-3">
            <WarningIcon className="h-5 w-5 flex-none text-bad" />
            <div className="text-[13.5px] leading-relaxed text-ink">
              {invoice.status === "ocr_failed" ? (
                <>
                  Nepodařilo se přečíst text z tohoto dokladu. Zkus nahrát ostřejší nebo lépe osvětlený sken či fotku.
                </>
              ) : (
                <>
                  Text se přečíst podařilo, ale nepodařilo se z něj spolehlivě vytáhnout částky a položky. Zkontroluj
                  doklad ručně, nebo ho nahraj znovu v lepší kvalitě.
                </>
              )}
            </div>
          </div>
          {invoice.raw_ocr_text && (
            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowRawText((value) => !value)}
                className="text-[12.5px] font-semibold text-accent hover:underline"
              >
                {showRawText ? "Skrýt přečtený text" : "Zobrazit přečtený text (OCR)"}
              </button>
              {showRawText && (
                <pre className="mt-3 max-h-64 overflow-auto rounded-[12px] border border-border bg-surface-2 p-3 text-[12px] leading-relaxed text-ink-muted">
                  {invoice.raw_ocr_text}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {!isPending && !isFailed && (
        <>
          <div className="glass-panel overflow-hidden rounded-[22px]">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-[13.5px]">
                <thead>
                  <tr>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Popis položky
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Kategorie
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Částka
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Jistota
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const isLow = item.confidence_score < LOW_CONFIDENCE_THRESHOLD;
                    return (
                      <tr key={item.id} className={isLow ? "bg-bad-soft" : ""}>
                        <td className={`group px-[18px] py-3 ${isLow ? "border-transparent" : "border-t border-border"}`}>
                          <div className="flex items-center gap-2">
                            {isLow && <WarningIcon className="h-3.5 w-3.5 flex-none text-bad" />}
                            <div className="min-w-0 flex-1">
                              <EditableCell
                                value={item.description}
                                onSave={(value) =>
                                  updateItem.mutate({ itemId: item.id, invoiceId: invoice.id, changes: { description: value } })
                                }
                              />
                            </div>
                            <EditIcon className="h-3.5 w-3.5 flex-none text-ink-muted opacity-0 transition-opacity group-hover:opacity-100" />
                          </div>
                        </td>
                        <td className={`px-[18px] py-3 ${isLow ? "border-transparent" : "border-t border-border"}`}>
                          <EditableCell
                            value={item.category}
                            onSave={(value) =>
                              updateItem.mutate({ itemId: item.id, invoiceId: invoice.id, changes: { category: value } })
                            }
                          />
                        </td>
                        <td className={`px-[18px] py-3 text-right ${isLow ? "border-transparent" : "border-t border-border"}`}>
                          <EditableCell
                            value={String(item.amount)}
                            type="number"
                            align="right"
                            monospace
                            onSave={(value) => {
                              const parsed = Number.parseFloat(value);
                              if (!Number.isNaN(parsed)) {
                                updateItem.mutate({ itemId: item.id, invoiceId: invoice.id, changes: { amount: parsed } });
                              }
                            }}
                          />
                        </td>
                        <td className={`px-[18px] py-3 ${isLow ? "border-transparent" : "border-t border-border"}`}>
                          <ConfidenceMeter score={item.confidence_score} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {invoice.total_amount !== null && (
                  <tfoot>
                    <tr>
                      <td colSpan={2} className="border-t border-border px-[18px] py-3.5 font-bold text-ink">
                        Celkem
                      </td>
                      <td className="border-t border-border px-[18px] py-3.5 text-right font-mono font-bold tabular-nums text-ink">
                        {formatAmount(invoice.total_amount, invoice.currency)}
                      </td>
                      <td className="border-t border-border" />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>

          {lowConfidenceItem && (
            <div className="glass-panel mt-4 flex items-start gap-2.5 rounded-[16px] p-3.5 text-[12.5px] leading-relaxed text-ink-muted">
              <WarningIcon className="mt-0.5 h-4 w-4 flex-none text-bad" />
              <div>
                <b className="text-ink">{lowConfidenceItem.description}</b> má nízkou jistotu OCR (
                {Math.round(lowConfidenceItem.confidence_score * 100)} %). Zkontroluj a případně oprav kliknutím na
                buňku v tabulce.
              </div>
            </div>
          )}

          {invoice.raw_ocr_text && (
            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowRawText((value) => !value)}
                className="text-[12.5px] font-semibold text-accent hover:underline"
              >
                {showRawText ? "Skrýt přečtený text" : "Zobrazit přečtený text (OCR)"}
              </button>
              {showRawText && (
                <pre className="mt-3 max-h-64 overflow-auto rounded-[12px] border border-border bg-surface-2 p-3 text-[12px] leading-relaxed text-ink-muted">
                  {invoice.raw_ocr_text}
                </pre>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

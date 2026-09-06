import { useState } from "react";
import { useInvoiceDetail } from "../hooks/useInvoiceDetail";
import { useInvoiceItems } from "../hooks/useInvoiceItems";
import { useUpdateItem } from "../hooks/useUpdateItem";
import { useUpdateInvoice } from "../hooks/useUpdateInvoice";
import { formatAmount, formatDate, formatDateTime } from "../lib/format";
import { StatusPill } from "./StatusPill";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { EditableCell } from "./EditableCell";
import { EditIcon, SpinnerIcon, WarningIcon } from "./icons";

const LOW_CONFIDENCE_THRESHOLD = 0.6;

export function InvoiceDetail({ invoiceId }: { invoiceId: number | null }) {
  const invoiceQuery = useInvoiceDetail(invoiceId);
  // Dokud faktura ještě běží OCR/LLM zpracováním, položky ještě neexistují -
  // pollujeme, ať se jakmile zpracování doběhne, tabulka sama objeví, aniž
  // by uživatel musel kliknout pryč a zpátky.
  const pendingStatus = invoiceQuery.data?.status;
  const isInvoicePending = pendingStatus === "uploaded" || pendingStatus === "processing";
  const itemsQuery = useInvoiceItems(invoiceId, isInvoicePending);
  const updateItem = useUpdateItem();
  const updateInvoice = useUpdateInvoice();
  const [showRawText, setShowRawText] = useState(false);

  if (invoiceId === null) {
    return (
      <section className="flex min-h-0 flex-1 items-center justify-center p-8">
        <p className="text-[14px] text-ink-muted">Vyber fakturu ze seznamu vlevo.</p>
      </section>
    );
  }

  const invoice = invoiceQuery.data;

  if (invoiceQuery.isLoading || !invoice) {
    return (
      <section className="flex min-h-0 flex-1 items-center justify-center p-8">
        <SpinnerIcon className="h-5 w-5 animate-spin text-ink-muted" />
      </section>
    );
  }

  const isPending = isInvoicePending;
  const isFailed = invoice.status === "ocr_failed" || invoice.status === "extraction_failed";
  const items = itemsQuery.data ?? [];

  const lowConfidenceItem = items.find((item) => item.confidence_score < LOW_CONFIDENCE_THRESHOLD);

  // Sloučená faktura může nést položky od různých dodavatelů/z různých dat - hlavička
  // faktury pak tuhle informaci nemůže vždy věrně shrnout jednou hodnotou, tak ji
  // v takovém případě zobrazíme zvlášť u každé položky.
  const distinctOrigins = new Set(
    items.map((item) => `${item.supplier_name ?? invoice.supplier_name ?? ""}__${item.invoice_date ?? invoice.invoice_date ?? ""}`),
  );
  const showItemOrigin = distinctOrigins.size > 1;
  const columnCount = showItemOrigin ? 6 : 4;

  // Jen když MÁ položka bez_DPH vyplněné - to se stane výhradně když to sám doklad uváděl
  // (viz llm.py), takže "chybí u některé položky" typicky znamená "dodavatel není plátce
  // DPH" a rozpad se tam prostě dopočítávat nemá.
  const vatBreakdown = (() => {
    if (items.length === 0 || items.some((item) => item.amount_without_vat === null)) return null;
    const vatBaseTotal = items.reduce((sum, item) => sum + (item.amount_without_vat ?? 0), 0);
    const rateTotals = new Map<number | null, number>();
    for (const item of items) {
      const vatAmount = item.amount - (item.amount_without_vat ?? 0);
      rateTotals.set(item.vat_rate, (rateTotals.get(item.vat_rate) ?? 0) + vatAmount);
    }
    const rateRows = Array.from(rateTotals.entries())
      .sort(([a], [b]) => (a ?? -1) - (b ?? -1))
      .map(([rate, amount]) => ({
        label: rate !== null ? `DPH ${rate} %` : "DPH",
        amount: Math.round(amount * 100) / 100,
      }));
    return { vatBaseTotal: Math.round(vatBaseTotal * 100) / 100, rateRows };
  })();

  return (
    <section className="min-h-0 min-w-0 flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <h2 className="m-0 mb-1" style={{ textWrap: "balance" }}>
            <EditableCell
              value={invoice.supplier_name ?? ""}
              displayValue={invoice.supplier_name ?? "Nerozpoznáno"}
              placeholder="Jméno dodavatele"
              padding="px-0 py-0"
              className="text-[22px] font-bold tracking-tight text-ink"
              onSave={(value) => updateInvoice.mutate({ invoiceId: invoice.id, changes: { supplier_name: value } })}
            />
          </h2>
          <div className="flex flex-wrap items-center gap-3.5 text-[13px] text-ink-muted">
            <StatusPill status={invoice.status} />
            <span>{invoice.original_filename}</span>
            <EditableCell
              value={invoice.invoice_date ?? ""}
              displayValue={invoice.invoice_date ? formatDate(invoice.invoice_date) : formatDateTime(invoice.created_at)}
              type="date"
              padding="px-0 py-0"
              className="text-[13px] text-ink-muted"
              onSave={(value) => updateInvoice.mutate({ invoiceId: invoice.id, changes: { invoice_date: value } })}
            />
          </div>
        </div>
        {invoice.total_amount !== null && (
          <div className="text-right">
            <div className="flex items-baseline justify-end gap-1.5">
              <span className="font-mono text-[26px] font-semibold tabular-nums text-ink">
                {new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 0 }).format(invoice.total_amount)}
              </span>
              <span className="flex w-14 items-center justify-end gap-1 text-[15px] font-medium text-ink-muted">
                {invoice.currency_confidence < LOW_CONFIDENCE_THRESHOLD && (
                  <WarningIcon className="h-3.5 w-3.5 flex-none text-bad" />
                )}
                <EditableCell
                  value={invoice.currency}
                  align="right"
                  padding="px-0.5 py-0"
                  onSave={(value) => updateInvoice.mutate({ invoiceId: invoice.id, changes: { currency: value.toUpperCase() } })}
                />
              </span>
            </div>
            <div className="text-[12px] text-ink-muted">celkem</div>
          </div>
        )}
      </div>

      {invoice.currency_confidence < LOW_CONFIDENCE_THRESHOLD && (
        <div className="glass-panel mb-4 flex items-start gap-2.5 rounded-[16px] p-3.5 text-[12.5px] leading-relaxed text-ink-muted">
          <WarningIcon className="mt-0.5 h-4 w-4 flex-none text-bad" />
          <div>
            <b className="text-ink">Měna {invoice.currency} je jen odhad.</b> Doklad neobsahoval jasnou stopu po
            měně (symbol ani kód), zkontroluj prosím částky a měnu ručně - klikni na "{invoice.currency}" vpravo
            nahoře a oprav ji, pokud nesedí.
          </div>
        </div>
      )}

      {invoice.extraction_warning && (
        <div className="glass-panel mb-4 flex items-start gap-2.5 rounded-[16px] p-3.5 text-[12.5px] leading-relaxed text-ink-muted">
          <WarningIcon className="mt-0.5 h-4 w-4 flex-none text-warn" />
          <div>
            <b className="text-ink">Doklad může obsahovat další položky.</b> {invoice.extraction_warning}
          </div>
        </div>
      )}

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
                    {showItemOrigin && (
                      <>
                        <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                          Dodavatel
                        </th>
                        <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                          Datum
                        </th>
                      </>
                    )}
                    <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Popis položky
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Kategorie
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-center text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Přesnost
                    </th>
                    <th className="px-[18px] pb-2.5 pt-3.5 text-right text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      Částka
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const isLow = item.confidence_score < LOW_CONFIDENCE_THRESHOLD;
                    return (
                      <tr key={item.id} className={isLow ? "bg-bad-soft" : ""}>
                        {showItemOrigin && (
                          <>
                            <td className={`px-[18px] py-3 text-ink-muted ${isLow ? "border-transparent" : "border-t border-border"}`}>
                              {item.supplier_name ?? invoice.supplier_name ?? "—"}
                            </td>
                            <td className={`px-[18px] py-3 text-ink-muted ${isLow ? "border-transparent" : "border-t border-border"}`}>
                              {formatDate(item.invoice_date ?? invoice.invoice_date)}
                            </td>
                          </>
                        )}
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
                        <td className={`px-[18px] py-3 ${isLow ? "border-transparent" : "border-t border-border"}`}>
                          <ConfidenceMeter score={item.confidence_score} />
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
                      </tr>
                    );
                  })}
                </tbody>
                {invoice.total_amount !== null && (
                  <tfoot>
                    {vatBreakdown && (
                      <>
                        <tr>
                          <td colSpan={columnCount - 1} className="border-t border-border px-[18px] py-2 text-right text-[12.5px] text-ink-muted">
                            Základ daně
                          </td>
                          <td className="border-t border-border px-[18px] py-2 text-right font-mono text-[12.5px] tabular-nums text-ink-muted">
                            {formatAmount(vatBreakdown.vatBaseTotal, invoice.currency)}
                          </td>
                        </tr>
                        {vatBreakdown.rateRows.map((rateRow) => (
                          <tr key={rateRow.label}>
                            <td colSpan={columnCount - 1} className="px-[18px] py-2 text-right text-[12.5px] text-ink-muted">
                              {rateRow.label}
                            </td>
                            <td className="px-[18px] py-2 text-right font-mono text-[12.5px] tabular-nums text-ink-muted">
                              {formatAmount(rateRow.amount, invoice.currency)}
                            </td>
                          </tr>
                        ))}
                      </>
                    )}
                    <tr>
                      <td colSpan={columnCount - 1} className="border-t border-border px-[18px] py-3.5 font-bold text-ink">
                        {vatBreakdown ? "Celkem s DPH" : "Celkem"}
                      </td>
                      <td className="border-t border-border px-[18px] py-3.5 text-right font-mono font-bold tabular-nums text-ink">
                        {formatAmount(invoice.total_amount, invoice.currency)}
                      </td>
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

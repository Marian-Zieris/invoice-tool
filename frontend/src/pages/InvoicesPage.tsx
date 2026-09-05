import { useEffect, useState } from "react";
import { useInvoices } from "../hooks/useInvoices";
import { downloadInvoiceExport, ApiError } from "../api/client";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";
import { InvoiceList } from "../components/InvoiceList";
import { InvoiceDetail } from "../components/InvoiceDetail";

export function InvoicesPage() {
  const invoicesQuery = useInvoices();
  const invoices = invoicesQuery.data ?? [];

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedForExport, setSelectedForExport] = useState<Set<number>>(new Set());
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedId === null && invoices.length > 0) {
      setSelectedId(invoices[0].id);
    }
  }, [invoices, selectedId]);

  function handleDeleted(id: number) {
    setSelectedForExport((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
    setSelectedId((current) => (current === id ? null : current));
  }

  function handleMerged(newInvoiceId: number) {
    setSelectedForExport(new Set());
    setSelectedId(newInvoiceId);
  }

  function toggleExport(id: number) {
    setSelectedForExport((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelectedForExport((current) =>
      current.size === invoices.length ? new Set() : new Set(invoices.map((invoice) => invoice.id)),
    );
  }

  async function handleExport() {
    setExportError(null);
    setIsExporting(true);
    try {
      await downloadInvoiceExport(Array.from(selectedForExport));
    } catch (error) {
      setExportError(error instanceof ApiError ? error.message : "Export se nezdařil.");
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar invoices={invoicesQuery.data} />
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <InvoiceList
            invoices={invoices}
            isLoading={invoicesQuery.isLoading}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onDeleted={handleDeleted}
            onMerged={handleMerged}
            selectedForExport={selectedForExport}
            onToggleExport={toggleExport}
            onToggleAll={toggleAll}
            onExport={handleExport}
            isExporting={isExporting}
          />
          <InvoiceDetail invoiceId={selectedId} />
        </div>
        {exportError && (
          <p className="border-t border-border px-8 py-2 text-[12.5px] text-bad">{exportError}</p>
        )}
      </div>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceDetail } from "../api/types";

const ACTIVE_STATUSES = new Set<string>(["uploaded", "processing"]);

export function useInvoiceDetail(invoiceId: number | null) {
  return useQuery({
    queryKey: ["invoice-detail", invoiceId],
    queryFn: () => api.get<InvoiceDetail>(`/invoices/${invoiceId}`),
    enabled: invoiceId !== null,
    // Bez tohohle appka po dokončení OCR/LLM zpracování v detailu faktury,
    // na kterou se uživatel právě dívá, "nic neuvidí" dokud neklikne pryč a
    // zpátky (queryKey se znovu nenačte samo) - viz useInvoices, stejný princip.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.has(status) ? 3000 : false;
    },
  });
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceDetail } from "../api/types";

export function useInvoiceDetail(invoiceId: number | null) {
  return useQuery({
    queryKey: ["invoice-detail", invoiceId],
    queryFn: () => api.get<InvoiceDetail>(`/invoices/${invoiceId}`),
    enabled: invoiceId !== null,
  });
}

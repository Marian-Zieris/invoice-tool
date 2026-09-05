import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LineItem } from "../api/types";

export function useInvoiceItems(invoiceId: number | null) {
  return useQuery({
    queryKey: ["invoice-items", invoiceId],
    queryFn: () => api.get<LineItem[]>(`/invoices/${invoiceId}/items`),
    enabled: invoiceId !== null,
  });
}

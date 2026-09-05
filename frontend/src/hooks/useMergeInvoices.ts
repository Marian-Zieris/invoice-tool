import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceSummary } from "../api/types";

export function useMergeInvoices() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (invoiceIds: number[]) => api.post<InvoiceSummary>("/invoices/merge", { invoice_ids: invoiceIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

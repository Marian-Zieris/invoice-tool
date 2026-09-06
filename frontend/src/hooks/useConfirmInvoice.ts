import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceDetail } from "../api/types";

export function useConfirmInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (invoiceId: number) => api.post<InvoiceDetail>(`/invoices/${invoiceId}/confirm`),
    onSuccess: (_data, invoiceId) => {
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

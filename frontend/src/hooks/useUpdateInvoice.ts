import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceDetail } from "../api/types";

interface UpdateInvoiceVariables {
  invoiceId: number;
  changes: Partial<Pick<InvoiceDetail, "supplier_name" | "invoice_date" | "total_amount" | "currency">>;
}

export function useUpdateInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ invoiceId, changes }: UpdateInvoiceVariables) =>
      api.patch<InvoiceDetail>(`/invoices/${invoiceId}`, changes),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", variables.invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

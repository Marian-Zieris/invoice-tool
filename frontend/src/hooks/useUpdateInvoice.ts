import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceDetail } from "../api/types";

interface UpdateInvoiceVariables {
  invoiceId: number;
  // total_amount se sem záměrně nedává - je to vždy odvozený součet položek, ne
  // samostatná editovatelná hodnota (viz app/routers/invoices.py InvoiceUpdate).
  changes: Partial<Pick<InvoiceDetail, "supplier_name" | "invoice_date" | "currency">>;
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

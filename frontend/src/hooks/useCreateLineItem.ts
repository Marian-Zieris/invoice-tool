import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LineItem } from "../api/types";

export function useCreateLineItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (invoiceId: number) => api.post<LineItem>(`/invoices/${invoiceId}/items`),
    onSuccess: (_data, invoiceId) => {
      queryClient.invalidateQueries({ queryKey: ["invoice-items", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

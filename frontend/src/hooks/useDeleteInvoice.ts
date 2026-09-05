import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function useDeleteInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (invoiceId: number) => api.delete<null>(`/invoices/${invoiceId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

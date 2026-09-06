import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

interface DeleteItemVariables {
  itemId: number;
  invoiceId: number;
}

export function useDeleteLineItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId }: DeleteItemVariables) => api.delete<null>(`/items/${itemId}`),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["invoice-items", variables.invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", variables.invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

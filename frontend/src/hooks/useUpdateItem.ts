import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LineItem } from "../api/types";

interface UpdateItemVariables {
  itemId: number;
  invoiceId: number;
  changes: Partial<Pick<LineItem, "description" | "category" | "amount">>;
}

export function useUpdateItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, changes }: UpdateItemVariables) => api.patch<LineItem>(`/items/${itemId}`, changes),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["invoice-items", variables.invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", variables.invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

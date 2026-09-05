import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "./adminClient";

export function useAdminCustomers(enabled: boolean) {
  return useQuery({
    queryKey: ["admin-customers"],
    queryFn: () => adminApi.listCustomers(),
    enabled,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.createCustomer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-customers"] }),
  });
}

export function useUploadTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ customerId, file }: { customerId: number; file: File }) => adminApi.uploadTemplate(customerId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-customers"] }),
  });
}

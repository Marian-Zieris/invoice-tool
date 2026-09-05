import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, type UploadTemplateOptions } from "./adminClient";

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

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (customerId: number) => adminApi.deleteCustomer(customerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-customers"] }),
  });
}

export function useUploadTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ customerId, options }: { customerId: number; options: UploadTemplateOptions }) =>
      adminApi.uploadTemplate(customerId, options),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-customers"] }),
  });
}

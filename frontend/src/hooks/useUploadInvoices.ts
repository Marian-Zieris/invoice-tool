import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function useUploadInvoices() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (files: FileList) => {
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append("files", file));
      return api.upload("/invoices/upload", formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

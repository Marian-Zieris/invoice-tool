import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export interface UploadResultEntry {
  invoice_id?: number;
  original_filename: string;
  status: "uploaded" | "rejected";
  reason?: string;
  duplicate_of_invoice_id?: number;
}

export function useUploadInvoices() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      return api.upload<UploadResultEntry[]>("/invoices/upload", formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LineItem } from "../api/types";

export function useInvoiceItems(invoiceId: number | null, poll: boolean = false) {
  return useQuery({
    queryKey: ["invoice-items", invoiceId],
    queryFn: () => api.get<LineItem[]>(`/invoices/${invoiceId}/items`),
    enabled: invoiceId !== null,
    // `poll` říká volající straně (InvoiceDetail.tsx), jestli je faktura ještě
    // ve zpracování - položky samy o sobě nenesou žádný status, na základě
    // kterého by šlo o tomhle rozhodnout samostatně.
    refetchInterval: poll ? 3000 : false,
  });
}

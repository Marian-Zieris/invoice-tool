import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InvoiceSummary } from "../api/types";

const ACTIVE_STATUSES = new Set<string>(["uploaded", "processing"]);

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceSummary[]>("/invoices"),
    refetchInterval: (query) => {
      const invoices = query.state.data;
      const hasActive = invoices?.some((invoice) => ACTIVE_STATUSES.has(invoice.status));
      return hasActive ? 3000 : false;
    },
  });
}

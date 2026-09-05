export type InvoiceStatus =
  | "uploaded"
  | "processing"
  | "needs_review"
  | "reviewed"
  | "exported"
  | "ocr_failed"
  | "extraction_failed";

export interface InvoiceSummary {
  id: number;
  original_filename: string;
  status: InvoiceStatus;
  supplier_name: string | null;
  invoice_date: string | null;
  total_amount: number | null;
  currency: string;
  created_at: string;
}

export interface InvoiceDetail extends InvoiceSummary {
  raw_ocr_text: string;
}

export interface LineItem {
  id: number;
  invoice_id: number;
  description: string;
  category: string;
  amount: number;
  confidence_score: number;
  is_corrected: boolean;
  supplier_name: string | null;
  invoice_date: string | null;
  amount_without_vat: number | null;
  vat_rate: number | null;
}

export interface Customer {
  id: number;
  email: string;
}

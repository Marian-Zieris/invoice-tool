import { ApiError } from "../api/client";

const ADMIN_KEY_STORAGE = "dokladovna_admin_key";

export function getAdminKey(): string | null {
  try {
    return sessionStorage.getItem(ADMIN_KEY_STORAGE);
  } catch {
    return null;
  }
}

export function setAdminKey(key: string | null): void {
  try {
    if (key) sessionStorage.setItem(ADMIN_KEY_STORAGE, key);
    else sessionStorage.removeItem(ADMIN_KEY_STORAGE);
  } catch {
    // admin session just won't persist across reloads - acceptable
  }
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message: string;
  error_code?: string;
}

async function adminRequest<T>(path: string, method: string, body?: unknown, isFormData = false): Promise<T> {
  const key = getAdminKey();
  const headers: Record<string, string> = {};
  if (key) headers["X-Admin-Key"] = key;

  let requestBody: BodyInit | undefined;
  if (body !== undefined) {
    if (isFormData) {
      requestBody = body as FormData;
    } else {
      headers["Content-Type"] = "application/json";
      requestBody = JSON.stringify(body);
    }
  }

  const response = await fetch(`/api${path}`, { method, headers, body: requestBody });
  const payload: ApiEnvelope<T> | null = await response.json().catch(() => null);

  if (!response.ok || !payload?.success) {
    throw new ApiError(payload?.message ?? `Chyba serveru (${response.status}).`, response.status, payload?.error_code);
  }
  return payload.data;
}

export interface CategoryRules {
  categories?: string[];
}

export interface ExcelTemplateConfig {
  template_path?: string;
  template_name?: string;
  sheet_name?: string;
  start_row?: number;
  columns?: string[];
  headers?: string[];
}

export interface AdminCustomer {
  id: number;
  email: string;
  excel_template_config: ExcelTemplateConfig;
  category_rules: CategoryRules;
}

export interface CreateCustomerPayload {
  email: string;
  password: string;
  category_rules?: CategoryRules;
}

export interface UploadTemplateOptions {
  file?: File;
  sheetName?: string;
  startRow?: number;
  columns?: string;
}

export const adminApi = {
  listCustomers: () => adminRequest<AdminCustomer[]>("/customers", "GET"),
  createCustomer: (payload: CreateCustomerPayload) => adminRequest<AdminCustomer>("/customers", "POST", payload),
  uploadTemplate: (customerId: number, options: UploadTemplateOptions) => {
    const formData = new FormData();
    if (options.file) formData.append("file", options.file);
    if (options.sheetName) formData.append("sheet_name", options.sheetName);
    if (options.startRow !== undefined) formData.append("start_row", String(options.startRow));
    if (options.columns) formData.append("columns", options.columns);
    return adminRequest<{ customer_id: number; excel_template_config: ExcelTemplateConfig }>(
      `/customers/${customerId}/template`,
      "POST",
      formData,
      true,
    );
  },
};

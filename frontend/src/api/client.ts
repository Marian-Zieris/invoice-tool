const TOKEN_KEY = "dokladovna_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // private browsing / storage disabled - session just won't persist across reloads
  }
}

export class ApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  isFormData?: boolean;
}

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message: string;
  error_code?: string;
}

interface FastApiValidationError {
  loc?: (string | number)[];
  msg?: string;
}

export function extractErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (typeof record.message === "string") return record.message;

    // FastAPI's own validation error shape (e.g. HTTP 422) doesn't go through api_error() -
    // it never has our {success, data, message} envelope, just a raw "detail".
    if (Array.isArray(record.detail)) {
      const details = record.detail as FastApiValidationError[];
      return details
        .map((item) => `${(item.loc ?? []).join(".")}: ${item.msg ?? "neplatná hodnota"}`)
        .join("; ");
    }
    if (typeof record.detail === "string") return record.detail;
  }
  return `Chyba serveru (${status}).`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    if (options.isFormData) {
      body = options.body as FormData;
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(`/api${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
  });

  if (response.status === 401 && path !== "/auth/login") {
    setToken(null);
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  const payload: ApiEnvelope<T> | null = await response.json().catch(() => null);

  if (!response.ok || !payload?.success) {
    throw new ApiError(extractErrorMessage(payload, response.status), response.status, payload?.error_code);
  }

  return payload.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData, isFormData: true }),
};

export async function downloadInvoiceExport(invoiceIds: number[]): Promise<void> {
  const token = getToken();
  const response = await fetch("/api/invoices/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ invoice_ids: invoiceIds }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(payload, response.status), response.status);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "faktury_export.xlsx";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

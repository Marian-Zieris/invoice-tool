import { useRef, useState, type FormEvent } from "react";
import { useAdminAuth } from "./AdminAuthContext";
import { useAdminCustomers, useCreateCustomer, useUploadTemplate } from "./hooks";
import { ApiError } from "../api/client";
import { ThemeToggle } from "../components/ThemeToggle";
import { SpinnerIcon, UploadIcon, LogoutIcon } from "../components/icons";

function parseCategories(raw: string): string[] {
  return raw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function NewCustomerForm() {
  const createCustomer = useCreateCustomer();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [categories, setCategories] = useState("materiál, práce, doprava, ostatní");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const customer = await createCustomer.mutateAsync({
        email,
        password,
        category_rules: { categories: parseCategories(categories) },
      });
      setSuccess(`Zákazník ${customer.email} vytvořen.`);
      setEmail("");
      setPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Vytvoření se nezdařilo.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="glass-panel flex flex-col gap-4 rounded-[22px] p-6">
      <h2 className="m-0 text-[16px] font-bold text-ink">Nový zákazník</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-muted">
          E-mail
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded-[10px] border border-border bg-surface-2 px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-muted">
          Heslo (min. 8 znaků)
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded-[10px] border border-border bg-surface-2 px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent"
          />
        </label>
      </div>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-muted">
        Kategorie položek (oddělené čárkou)
        <input
          type="text"
          value={categories}
          onChange={(event) => setCategories(event.target.value)}
          className="rounded-[10px] border border-border bg-surface-2 px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent"
        />
      </label>

      {error && <p className="text-[13px] text-bad">{error}</p>}
      {success && <p className="text-[13px] text-good">{success}</p>}

      <button
        type="submit"
        disabled={createCustomer.isPending}
        className="self-start rounded-[10px] bg-accent px-4 py-2.5 text-[13.5px] font-semibold text-accent-ink transition-transform hover:-translate-y-px disabled:opacity-60"
      >
        {createCustomer.isPending ? "Vytvářím…" : "Vytvořit zákazníka"}
      </button>
    </form>
  );
}

function TemplateCell({ customerId, templateName }: { customerId: number; templateName?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadTemplate = useUploadTemplate();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            setError(null);
            uploadTemplate.mutate(
              { customerId, file },
              { onError: (err) => setError(err instanceof ApiError ? err.message : "Nahrání selhalo.") },
            );
          }
          event.target.value = "";
        }}
      />
      <span className="truncate text-[12.5px] text-ink-muted">{templateName ?? "žádná šablona"}</span>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploadTemplate.isPending}
        className="flex flex-none items-center gap-1 rounded-[8px] border border-border bg-surface px-2.5 py-1 text-[12px] font-semibold text-ink transition-colors hover:bg-surface-2 disabled:opacity-50"
      >
        <UploadIcon className="h-3 w-3" />
        {uploadTemplate.isPending ? "…" : templateName ? "Nahradit" : "Nahrát"}
      </button>
      {error && <span className="text-[11.5px] text-bad">{error}</span>}
    </div>
  );
}

export function AdminDashboard() {
  const { lock } = useAdminAuth();
  const customersQuery = useAdminCustomers(true);
  const customers = customersQuery.data ?? [];

  return (
    <div className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 p-6 md:p-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="m-0 text-[19px] font-bold tracking-tight text-ink">Dokladovna · Admin</h1>
          <p className="mt-0.5 text-[13px] text-ink-muted">Správa zákaznických účtů a Excel šablon.</p>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            type="button"
            onClick={lock}
            className="flex items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 py-2.5 text-[13px] font-semibold text-ink transition-colors hover:bg-surface-2"
          >
            <LogoutIcon className="h-4 w-4" />
            Uzamknout
          </button>
        </div>
      </header>

      <NewCustomerForm />

      <section className="glass-panel rounded-[22px] p-6">
        <h2 className="m-0 mb-4 text-[16px] font-bold text-ink">Zákazníci ({customers.length})</h2>

        {customersQuery.isLoading && (
          <div className="flex items-center gap-2 py-6 text-[13.5px] text-ink-muted">
            <SpinnerIcon className="h-4 w-4 animate-spin" />
            Načítám…
          </div>
        )}

        {!customersQuery.isLoading && customers.length === 0 && (
          <p className="py-6 text-center text-[13.5px] text-ink-muted">Zatím žádní zákazníci.</p>
        )}

        {customers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[13.5px]">
              <thead>
                <tr>
                  <th className="px-3 pb-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    E-mail
                  </th>
                  <th className="px-3 pb-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    Kategorie
                  </th>
                  <th className="px-3 pb-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    Excel šablona
                  </th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="border-t border-border px-3 py-3 text-ink">{customer.email}</td>
                    <td className="border-t border-border px-3 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {(customer.category_rules.categories ?? []).map((category) => (
                          <span key={category} className="rounded-md bg-surface-2 px-2 py-0.5 text-[11.5px] text-ink-muted">
                            {category}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="border-t border-border px-3 py-3">
                      <TemplateCell customerId={customer.id} templateName={customer.excel_template_config.template_name} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

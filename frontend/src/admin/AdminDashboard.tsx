import { useRef, useState, type FormEvent } from "react";
import { useAdminAuth } from "./AdminAuthContext";
import { useAdminCustomers, useCreateCustomer, useUpdateCategories, useUploadTemplate } from "./hooks";
import type { ExcelTemplateConfig } from "./adminClient";
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

function CategoriesCell({ customerId, categories }: { customerId: number; categories: string[] }) {
  const updateCategories = useUpdateCategories();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(categories.join(", "));
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const parsed = parseCategories(draft);
    if (parsed.length === 0) {
      setError("Zadej aspoň jednu kategorii.");
      return;
    }
    setError(null);
    updateCategories.mutate(
      { customerId, categories: parsed },
      {
        onSuccess: () => setEditing(false),
        onError: (err) => setError(err instanceof ApiError ? err.message : "Uložení selhalo."),
      },
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(categories.join(", "));
          setEditing(true);
        }}
        className="flex flex-wrap items-center gap-1.5 rounded-[8px] px-1 py-1 text-left transition-colors hover:bg-surface-2"
      >
        {categories.length === 0 && <span className="text-[12px] text-ink-muted">žádné — klik pro nastavení</span>}
        {categories.map((category) => (
          <span key={category} className="rounded-md bg-surface-2 px-2 py-0.5 text-[11.5px] text-ink-muted">
            {category}
          </span>
        ))}
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-w-[220px] flex-col gap-2 rounded-[12px] border border-border bg-surface-2 p-3">
      <input
        autoFocus
        type="text"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="materiál, práce, doprava, ostatní"
        className="rounded-[7px] border border-border bg-surface px-2 py-1.5 text-[12.5px] text-ink outline-none focus:border-accent"
      />
      {error && <p className="text-[11.5px] text-bad">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={updateCategories.isPending}
          className="rounded-[8px] bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink disabled:opacity-60"
        >
          {updateCategories.isPending ? "Ukládám…" : "Uložit"}
        </button>
        <button type="button" onClick={() => setEditing(false)} className="text-[11.5px] text-ink-muted hover:text-ink">
          Zrušit
        </button>
      </div>
    </form>
  );
}

const KNOWN_COLUMN_KEYS = [
  "invoice_id",
  "original_filename",
  "supplier_name",
  "invoice_date",
  "description",
  "category",
  "amount",
  "currency",
  "confidence_score",
  "is_corrected",
];

function TemplateCell({ customerId, template }: { customerId: number; template: ExcelTemplateConfig }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadTemplate = useUploadTemplate();
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetName, setSheetName] = useState(template.sheet_name ?? "");
  const [startRow, setStartRow] = useState(String(template.start_row ?? 2));
  const [columns, setColumns] = useState((template.columns ?? []).join(","));

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file && !template.template_path) {
      setError("Vyber soubor šablony.");
      return;
    }
    setError(null);
    uploadTemplate.mutate(
      {
        customerId,
        options: {
          file: file ?? undefined,
          sheetName: sheetName || undefined,
          startRow: startRow ? Number(startRow) : undefined,
          columns: columns || undefined,
        },
      },
      {
        onSuccess: () => setExpanded(false),
        onError: (err) => setError(err instanceof ApiError ? err.message : "Uložení selhalo."),
      },
    );
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="flex items-center gap-2 rounded-[8px] px-1 py-1 text-left transition-colors hover:bg-surface-2"
      >
        <UploadIcon className="h-3.5 w-3.5 flex-none text-ink-muted" />
        <span className="truncate text-[12.5px] text-ink">
          {template.template_name ?? <span className="text-ink-muted">žádná šablona — klik pro nastavení</span>}
        </span>
        {template.columns && (
          <span className="flex-none text-[11px] text-ink-muted">({template.columns.length} sloupců)</span>
        )}
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-w-[260px] flex-col gap-2 rounded-[12px] border border-border bg-surface-2 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-semibold text-ink">
          {template.template_name ? "Upravit šablonu" : "Nahrát šablonu"}
        </span>
        <button type="button" onClick={() => setExpanded(false)} className="text-[11px] text-ink-muted hover:text-ink">
          Zavřít
        </button>
      </div>

      <label className="flex flex-col gap-1 text-[11px] font-medium text-ink-muted">
        Soubor {template.template_name && "(ponech prázdné pro zachování stávajícího)"}
        <input ref={inputRef} type="file" accept=".xlsx,.xls" className="text-[11.5px]" />
      </label>

      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-[11px] font-medium text-ink-muted">
          List
          <input
            type="text"
            value={sheetName}
            onChange={(event) => setSheetName(event.target.value)}
            placeholder="první list"
            className="rounded-[7px] border border-border bg-surface px-2 py-1.5 text-[12px] text-ink outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-medium text-ink-muted">
          Od řádku
          <input
            type="number"
            min={1}
            value={startRow}
            onChange={(event) => setStartRow(event.target.value)}
            className="rounded-[7px] border border-border bg-surface px-2 py-1.5 text-[12px] text-ink outline-none focus:border-accent"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1 text-[11px] font-medium text-ink-muted">
        Sloupce v pořadí, oddělené čárkou
        <input
          type="text"
          value={columns}
          onChange={(event) => setColumns(event.target.value)}
          placeholder="supplier_name,invoice_date,description,category,amount,currency"
          className="rounded-[7px] border border-border bg-surface px-2 py-1.5 font-mono text-[11.5px] text-ink outline-none focus:border-accent"
        />
        <span className="text-[10.5px] leading-snug text-ink-muted">Platné klíče: {KNOWN_COLUMN_KEYS.join(", ")}</span>
      </label>

      {error && <p className="text-[11.5px] text-bad">{error}</p>}

      <button
        type="submit"
        disabled={uploadTemplate.isPending}
        className="self-start rounded-[8px] bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink disabled:opacity-60"
      >
        {uploadTemplate.isPending ? "Ukládám…" : "Uložit"}
      </button>
    </form>
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
                      <CategoriesCell customerId={customer.id} categories={customer.category_rules.categories ?? []} />
                    </td>
                    <td className="border-t border-border px-3 py-3">
                      <TemplateCell customerId={customer.id} template={customer.excel_template_config} />
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

import { useState, type FormEvent } from "react";
import { Sidebar } from "../components/Sidebar";
import { ThemeToggle } from "../components/ThemeToggle";
import { SpinnerIcon } from "../components/icons";
import { useMyProfile } from "../hooks/useMyProfile";
import { useUpdateMyCategories } from "../hooks/useUpdateMyCategories";
import { ApiError } from "../api/client";

export function SettingsPage() {
  const profileQuery = useMyProfile();
  const updateCategories = useUpdateMyCategories();
  const [newCategory, setNewCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  const categories = profileQuery.data?.category_rules.categories ?? [];

  function save(next: string[]) {
    setError(null);
    updateCategories.mutate(next, {
      onError: (err) => setError(err instanceof ApiError ? err.message : "Uložení selhalo."),
    });
  }

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    const trimmed = newCategory.trim();
    if (!trimmed) return;
    if (categories.some((category) => category.toLowerCase() === trimmed.toLowerCase())) {
      setNewCategory("");
      return;
    }
    save([...categories, trimmed]);
    setNewCategory("");
  }

  function handleRemove(category: string) {
    const next = categories.filter((existing) => existing !== category);
    if (next.length === 0) {
      setError("Musí zůstat aspoň jedna kategorie.");
      return;
    }
    save(next);
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-8 py-5">
          <div>
            <h1 className="m-0 text-[19px] font-bold tracking-tight text-ink" style={{ textWrap: "balance" }}>
              Nastavení
            </h1>
            <p className="mt-0.5 text-[13px] text-ink-muted">{profileQuery.data?.email}</p>
          </div>
          <ThemeToggle />
        </header>

        <div className="max-w-lg p-6 md:p-8">
          <section className="glass-panel rounded-[22px] p-6">
            <h2 className="m-0 mb-1 text-[16px] font-bold text-ink">Kategorie položek</h2>
            <p className="mb-4 text-[13px] leading-relaxed text-ink-muted">
              Podle tohohle seznamu AI třídí položky na fakturách při zpracování. Uprav si ho podle
              vlastního účetnictví — projeví se to hned u dalších nahraných dokladů.
            </p>

            {profileQuery.isLoading ? (
              <div className="flex items-center gap-2 py-4 text-[13.5px] text-ink-muted">
                <SpinnerIcon className="h-4 w-4 animate-spin" />
                Načítám…
              </div>
            ) : (
              <>
                <div className="mb-4 flex flex-wrap gap-2">
                  {categories.map((category) => (
                    <span
                      key={category}
                      className="flex items-center gap-1.5 rounded-full bg-surface-2 py-1 pl-3 pr-1.5 text-[12.5px] text-ink"
                    >
                      {category}
                      <button
                        type="button"
                        onClick={() => handleRemove(category)}
                        disabled={updateCategories.isPending}
                        aria-label={`Odebrat kategorii ${category}`}
                        className="flex h-4 w-4 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-bad-soft hover:text-bad disabled:opacity-50"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>

                <form onSubmit={handleAdd} className="flex gap-2">
                  <input
                    type="text"
                    value={newCategory}
                    onChange={(event) => setNewCategory(event.target.value)}
                    placeholder="Nová kategorie…"
                    className="flex-1 rounded-[10px] border border-border bg-surface-2 px-3 py-2 text-[13.5px] text-ink outline-none focus:border-accent"
                  />
                  <button
                    type="submit"
                    disabled={updateCategories.isPending || !newCategory.trim()}
                    className="rounded-[10px] bg-accent px-4 py-2 text-[13px] font-semibold text-accent-ink transition-transform hover:-translate-y-px disabled:opacity-50"
                  >
                    Přidat
                  </button>
                </form>

                {error && <p className="mt-3 text-[12.5px] text-bad">{error}</p>}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

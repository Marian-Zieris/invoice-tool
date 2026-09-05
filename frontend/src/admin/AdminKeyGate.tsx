import { useState, type FormEvent } from "react";
import { useAdminAuth } from "./AdminAuthContext";
import { ApiError } from "../api/client";

export function AdminKeyGate() {
  const { unlock } = useAdminAuth();
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await unlock(key);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Neplatný admin klíč." : "Nepodařilo se ověřit klíč.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="glass-panel w-full max-w-sm rounded-[22px] p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="flex h-8 w-8 flex-none items-center justify-center rounded-[10px] bg-accent text-[16px] font-bold text-accent-ink">
            D
          </div>
          <div className="text-[18px] font-bold tracking-tight text-ink">Dokladovna · Admin</div>
        </div>

        <h1 className="m-0 mb-1 text-[20px] font-bold text-ink">Admin klíč</h1>
        <p className="mb-6 text-[13.5px] text-ink-muted">
          Zadej hodnotu <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[12px]">ADMIN_API_KEY</code> z{" "}
          <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[12px]">.env</code>.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="password"
            required
            autoFocus
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder="Admin klíč"
            className="rounded-[10px] border border-border bg-surface-2 px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent"
          />

          {error && <p className="text-[13px] text-bad">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="mt-1 rounded-[10px] bg-accent px-4 py-2.5 text-[14px] font-semibold text-accent-ink transition-transform hover:-translate-y-px disabled:opacity-60"
          >
            {submitting ? "Ověřuji…" : "Odemknout"}
          </button>
        </form>
      </div>
    </div>
  );
}

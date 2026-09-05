import { useTheme } from "../hooks/useTheme";
import { MoonIcon, SunIcon } from "./icons";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className="glass-panel fixed right-4 top-4 z-50 flex items-center gap-0.5 rounded-full p-1"
      role="group"
      aria-label="Světlý nebo tmavý režim"
    >
      <button
        type="button"
        aria-pressed={theme === "dark"}
        onClick={() => setTheme("dark")}
        className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
          theme === "dark" ? "bg-accent text-accent-ink" : "text-ink-muted hover:text-ink"
        }`}
      >
        <MoonIcon className="h-3.5 w-3.5" />
        Tmavý
      </button>
      <button
        type="button"
        aria-pressed={theme === "light"}
        onClick={() => setTheme("light")}
        className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
          theme === "light" ? "bg-accent text-accent-ink" : "text-ink-muted hover:text-ink"
        }`}
      >
        <SunIcon className="h-3.5 w-3.5" />
        Světlý
      </button>
    </div>
  );
}

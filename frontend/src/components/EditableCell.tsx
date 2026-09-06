import { useState } from "react";

interface EditableCellProps {
  value: string;
  onSave: (value: string) => void;
  type?: "text" | "number" | "date";
  align?: "left" | "right";
  monospace?: boolean;
  padding?: string;
  /** Co se zobrazí v klidovém (needitovaném) stavu, když se má lišit od
   * skutečné editovatelné hodnoty - typicky hezčí formát data nebo placeholder
   * jako "Nerozpoznáno" pro prázdnou hodnotu, aniž by šel omylem uložit jako
   * doslovný text. */
  displayValue?: string;
  placeholder?: string;
  className?: string;
}

export function EditableCell({
  value,
  onSave,
  type = "text",
  align = "left",
  monospace = false,
  padding = "px-2 py-1",
  displayValue,
  placeholder,
  className = "",
}: EditableCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const alignClass = align === "right" ? "text-right" : "text-left";
  const fontClass = monospace ? "font-mono tabular-nums" : "";

  function commit() {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed !== "" && trimmed !== value) {
      onSave(trimmed);
    } else {
      setDraft(value);
    }
  }

  if (editing) {
    return (
      <input
        autoFocus
        type={type}
        step={type === "number" ? "0.01" : undefined}
        value={draft}
        placeholder={placeholder}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") (event.target as HTMLInputElement).blur();
          if (event.key === "Escape") {
            setDraft(value);
            setEditing(false);
          }
        }}
        className={`w-full rounded-md border border-accent bg-surface ${padding} text-[13.5px] text-ink outline-none ${alignClass} ${fontClass} ${className}`}
      />
    );
  }

  return (
    <button
      type="button"
      onClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      className={`w-full rounded-md ${padding} transition-colors hover:bg-surface-2 ${alignClass} ${fontClass} ${className}`}
    >
      {displayValue ?? value}
    </button>
  );
}

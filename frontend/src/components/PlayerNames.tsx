import { useState } from "react";
import { X } from "lucide-react";

/** Name chips with a text box: Enter or comma adds, Backspace on an empty
 *  box removes the last one. */
export function PlayerNames({ value, onChange, placeholder = "e.g. donk666" }: { value: string[]; onChange: (names: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const parts = draft.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length) onChange([...value, ...parts.filter((p) => !value.includes(p))]);
    setDraft("");
  };
  return (
    <div className="flex min-h-10 flex-wrap items-center gap-1.5 border border-line-strong bg-black/25 px-2 py-1.5 focus-within:border-accent/60">
      {value.map((n) => (
        <span key={n} className="flex items-center gap-1 border border-accent/40 bg-accent/10 py-0.5 pl-2 pr-1 text-[14px]">
          {n}
          <button onClick={() => onChange(value.filter((x) => x !== n))} className="text-fg-faint hover:text-fg" aria-label={`Remove ${n}`}>
            <X className="size-3.5" />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add();
          } else if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
        }}
        onBlur={add}
        placeholder={value.length ? "Add another" : placeholder}
        className="min-w-24 flex-1 bg-transparent px-1 text-[14.5px] outline-none"
      />
    </div>
  );
}

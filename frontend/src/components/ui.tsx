import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Minus, Plus, X } from "lucide-react";
import { cn } from "../lib/cn";

// The CS2-flavoured building blocks: flat, square, condensed uppercase type.

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-ink hover:bg-accent-hi shadow-[0_0_24px_-6px] shadow-accent/60 disabled:bg-raised disabled:text-fg-faint disabled:shadow-none",
  secondary: "bg-white/[0.06] text-fg border border-line-strong hover:bg-white/[0.11] hover:border-white/25",
  ghost: "text-fg-muted hover:text-fg hover:bg-white/[0.06]",
  danger: "bg-bad/15 text-bad border border-bad/35 hover:bg-bad/25",
};

const SIZES = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-[15px] gap-2",
  lg: "h-14 px-7 text-[20px] gap-3",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: keyof typeof SIZES }) {
  return (
    <button
      {...props}
      className={cn(
        "display inline-flex shrink-0 items-center justify-center rounded-sm font-semibold transition active:translate-y-px disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    />
  );
}

/** Translucent slate panel with an optional uppercase header. */
export function Panel({
  title,
  aside,
  className,
  bodyClassName,
  children,
}: {
  title?: ReactNode;
  aside?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("border border-line bg-panel/75 backdrop-blur-xl", className)}>
      {title && (
        <header className="flex h-11 items-center justify-between gap-3 border-b border-line bg-white/[0.025] px-4">
          <h2 className="display text-[15px] font-semibold text-fg-muted">{title}</h2>
          {aside}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("display text-[12.5px] font-semibold tracking-[0.12em] text-fg-faint", className)}>{children}</div>;
}

/** − value + */
export function Stepper({
  value,
  onDec,
  onInc,
  title,
}: {
  value: ReactNode;
  onDec: () => void;
  onInc: () => void;
  title?: string;
}) {
  const btn = "grid size-8 place-items-center text-fg-muted transition hover:bg-white/[0.08] hover:text-fg active:bg-white/[0.12]";
  return (
    <div className="inline-flex items-center border border-line-strong bg-black/20" title={title}>
      <button className={btn} onClick={onDec} aria-label="Fewer">
        <Minus className="size-3.5" />
      </button>
      <div className="display min-w-12 border-x border-line-strong text-center text-[16px] font-semibold leading-8 tabular">{value}</div>
      <button className={btn} onClick={onInc} aria-label="More">
        <Plus className="size-3.5" />
      </button>
    </div>
  );
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label?: string }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={cn(
        "relative h-6 w-11 shrink-0 border transition-colors",
        on ? "border-accent bg-accent/25" : "border-line-strong bg-black/25",
      )}
    >
      <motion.span
        className={cn("absolute top-[3px] size-4", on ? "bg-accent" : "bg-fg-faint")}
        animate={{ left: on ? 23 : 3 }}
        transition={{ type: "spring", stiffness: 600, damping: 35 }}
      />
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  width = 560,
  dismissable = true,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  width?: number;
  dismissable?: boolean;
}) {
  useEffect(() => {
    if (!open || !dismissable) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, dismissable, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(e) => dismissable && e.target === e.currentTarget && onClose()}
        >
          <motion.div
            role="dialog"
            className="w-full border border-line-strong bg-panel shadow-2xl shadow-black/60"
            style={{ maxWidth: width }}
            initial={{ y: 14, scale: 0.98 }}
            animate={{ y: 0, scale: 1 }}
            exit={{ y: 8, opacity: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          >
            <header className="flex h-12 items-center justify-between border-b border-line bg-white/[0.03] pl-5 pr-2">
              <h2 className="display text-[18px] font-semibold">{title}</h2>
              {dismissable && (
                <button onClick={onClose} className="grid size-9 place-items-center text-fg-muted hover:text-fg" aria-label="Close">
                  <X className="size-4.5" />
                </button>
              )}
            </header>
            <div className="p-5">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

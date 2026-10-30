import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, Check, RotateCw, X } from "lucide-react";
import { api, useChaosEvent, type ModelInfo, type ModelState, type ModelsError } from "../bridge";
import { Backdrop } from "../components/Backdrop";
import { Wordmark } from "../components/Wordmark";
import { fmtEta, fmtSize, fmtSpeed } from "../lib/format";
import { cn } from "../lib/cn";

const MB = 1 << 20;

interface Row {
  id: string;
  label: string;
  state: ModelState;
  done: number;
  total: number;
}

const ERROR_TITLES: Record<ModelsError["kind"], string> = {
  offline: "You seem to be offline",
  server: "The download server had a problem",
  checksum: "A download was damaged",
  disk: "Not enough disk space",
  other: "The download stopped",
};

/** Full-screen first-launch download of every model the config needs. The
 *  app isn't entered until it finishes, so Run never has to download. */
export function ModelGate({ models, onReady }: { models: ModelInfo[]; onReady: () => void }) {
  const [rows, setRows] = useState<Row[]>(() =>
    models.filter((m) => !m.ready).map((m) => ({ id: m.id, label: m.label, state: "waiting", done: 0, total: m.mb * MB })),
  );
  const [speed, setSpeed] = useState(0);
  const [eta, setEta] = useState<number | null>(null);
  const [error, setError] = useState<ModelsError | null>(null);
  const [finished, setFinished] = useState(false);

  const start = useCallback(() => {
    setError(null);
    setRows((rs) => rs.map((r) => (r.state === "error" ? { ...r, state: "waiting", done: 0 } : r)));
    void api.download_models();
  }, []);

  useEffect(start, [start]);

  useChaosEvent("models:progress", (p) => {
    setRows((rs) => rs.map((r) => (r.id === p.id ? { ...r, state: p.state, done: p.done, total: p.total } : r)));
    // Checking a finished file reports no speed; keep showing the last one.
    if (p.state === "downloading" && p.bytes_per_sec > 0) {
      setSpeed(p.bytes_per_sec);
      setEta(p.eta_sec);
    }
  });
  useChaosEvent("models:error", (e) => {
    setError(e);
    setSpeed(0);
    setEta(null);
    setRows((rs) => rs.map((r) => (r.id === e.id ? { ...r, state: "error" } : r)));
  });
  useChaosEvent("models:done", () => {
    setFinished(true);
    setTimeout(onReady, 1500);
  });

  const { done, total } = useMemo(
    () =>
      rows.reduce(
        (acc, r) => ({ done: acc.done + (r.state === "done" ? r.total : r.done), total: acc.total + r.total }),
        { done: 0, total: 0 },
      ),
    [rows],
  );
  const pct = total ? Math.min(100, (done / total) * 100) : 0;

  return (
    <div className="relative h-full overflow-hidden">
      <Backdrop intensity={finished ? 1.6 : 1} />
      <div className="relative z-10 grid h-full place-items-center overflow-y-auto px-6 py-10">
        <AnimatePresence mode="wait">
          {!finished ? (
            <motion.div
              key="downloading"
              className="w-full max-w-[560px]"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } }}
              exit={{ opacity: 0, scale: 0.97, filter: "blur(8px)", transition: { duration: 0.35 } }}
            >
              <Wordmark className="h-12 -ml-1" />
              <h1 className="display mt-10 text-[40px] font-bold leading-none tracking-[0.04em]">Getting CHAOS ready</h1>
              <p className="mt-3 max-w-[520px] text-[15px] leading-relaxed text-fg-muted">
                CHAOS uses a few AI models to read the killfeed and listen to voice chat. They download once, then
                you&apos;re straight in every time.
              </p>

              <div className="mt-10 flex items-end justify-between gap-6">
                <div className="display text-[64px] font-bold leading-none tabular">
                  {Math.floor(pct)}
                  <span className="text-[28px] text-fg-faint">%</span>
                </div>
                <div className="pb-1 text-right font-mono text-[12.5px] leading-6 text-fg-muted tabular">
                  <div>
                    {fmtSize(done)} <span className="text-fg-faint">of</span> {fmtSize(total)}
                  </div>
                  <div className="text-fg-faint">
                    {error ? "Paused" : speed > 0 ? `${fmtSpeed(speed)} · ${fmtEta(eta)}` : "Starting…"}
                  </div>
                </div>
              </div>
              <ProgressBar pct={pct} active={!error} failed={!!error} />

              <ul className="mt-8 overflow-hidden border border-line bg-panel/75 backdrop-blur-md">
                {rows.map((r, i) => (
                  <ModelRow key={r.id} row={r} first={i === 0} />
                ))}
              </ul>

              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-4 flex items-start gap-3.5 border border-bad/25 bg-bad/[0.06] p-4">
                      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-bad" />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{ERROR_TITLES[error.kind]}</div>
                        <div className="mt-1 text-[13.5px] leading-relaxed text-fg-muted">{error.message}</div>
                      </div>
                      <button
                        onClick={start}
                        className="display flex shrink-0 items-center gap-2 bg-accent px-3.5 py-2 text-[15px] font-semibold text-accent-ink transition hover:bg-accent-hi active:scale-[0.97]"
                      >
                        <RotateCw className="size-4" /> Retry
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ) : (
            <ReadyBurst key="ready" />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ProgressBar({ pct, active, failed }: { pct: number; active: boolean; failed: boolean }) {
  return (
    <div className="relative mt-4 h-2 overflow-hidden bg-raised">
      <motion.div
        className={cn("absolute inset-y-0 left-0 overflow-hidden", failed ? "bg-bad/70" : "bg-accent")}
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", stiffness: 60, damping: 20 }}
      >
        {active && (
          <motion.div
            className="absolute inset-0 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.45),transparent)]"
            initial={{ x: "-100%" }}
            animate={{ x: "100%" }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </motion.div>
      {active && <div className="absolute inset-y-0 left-0 blur-md bg-accent/40" style={{ width: `${pct}%` }} />}
    </div>
  );
}

const STATE_TEXT: Record<ModelState, string> = {
  waiting: "Waiting",
  downloading: "",
  verifying: "Checking",
  done: "Done",
  error: "Failed",
};

function ModelRow({ row, first }: { row: Row; first: boolean }) {
  const pct = row.total ? (row.done / row.total) * 100 : 0;
  const status = row.state === "downloading" ? `${Math.floor(pct)}%` : STATE_TEXT[row.state];
  return (
    <li className={cn("relative px-4 py-3.5", !first && "border-t border-line")}>
      <div className="flex items-center gap-3.5">
        <StateIcon state={row.state} pct={pct} />
        <div className={cn("min-w-0 flex-1 truncate text-[14.5px]", row.state === "waiting" ? "text-fg-muted" : "text-fg")}>
          {row.label}
        </div>
        <div className="font-mono text-[12.5px] text-fg-faint tabular">{fmtSize(row.total)}</div>
        <div
          className={cn(
            "w-[68px] text-right font-mono text-[12.5px] tabular",
            row.state === "done" && "text-secondary-hi",
            row.state === "error" && "text-bad",
            row.state === "downloading" && "text-accent",
            (row.state === "waiting" || row.state === "verifying") && "text-fg-muted",
          )}
        >
          {status}
        </div>
      </div>
      {row.state === "downloading" && (
        <motion.div
          className="absolute bottom-0 left-0 h-px bg-accent"
          animate={{ width: `${pct}%` }}
          transition={{ ease: "linear", duration: 0.12 }}
        />
      )}
    </li>
  );
}

function StateIcon({ state, pct }: { state: ModelState; pct: number }) {
  const R = 9;
  const C = 2 * Math.PI * R;
  return (
    <div className="relative grid size-6 shrink-0 place-items-center">
      <AnimatePresence initial={false}>
        {state === "done" ? (
          <motion.div
            key="done"
            initial={{ scale: 0.3, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 22 }}
            className="absolute inset-[1px] grid place-items-center rounded-full bg-secondary/30 text-secondary-hi"
          >
            <Check className="size-3.5" strokeWidth={3} />
          </motion.div>
        ) : state === "error" ? (
          <motion.div key="error" initial={{ scale: 0.5 }} animate={{ scale: 1 }} className="absolute inset-[1px] grid place-items-center rounded-full bg-bad/15 text-bad">
            <X className="size-3.5" strokeWidth={3} />
          </motion.div>
        ) : (
          <motion.svg key="ring" viewBox="0 0 24 24" className="absolute inset-[1px] -rotate-90" exit={{ scale: 0.6, opacity: 0 }}>
            <circle cx="12" cy="12" r={R} fill="none" strokeWidth="2.5" className="stroke-line-strong" />
            {state === "downloading" && (
              <circle
                cx="12" cy="12" r={R} fill="none" strokeWidth="2.5" strokeLinecap="round"
                className="stroke-accent transition-[stroke-dashoffset] duration-150"
                strokeDasharray={C}
                strokeDashoffset={C * (1 - pct / 100)}
              />
            )}
            {state === "verifying" && (
              <motion.circle
                cx="12" cy="12" r={R} fill="none" strokeWidth="2.5" strokeLinecap="round"
                className="stroke-fg-muted"
                strokeDasharray={`${C * 0.28} ${C}`}
                style={{ originX: "50%", originY: "50%" }}
                animate={{ rotate: 360 }}
                transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
              />
            )}
          </motion.svg>
        )}
      </AnimatePresence>
    </div>
  );
}

function ReadyBurst() {
  return (
    <motion.div
      className="flex flex-col items-center text-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.04, transition: { duration: 0.3 } }}
    >
      <div className="relative grid size-24 place-items-center">
        {[0, 1].map((i) => (
          <motion.div
            key={i}
            className="absolute inset-0 rounded-full border-2 border-secondary-hi"
            initial={{ scale: 0.6, opacity: 0.9 }}
            animate={{ scale: 2.1, opacity: 0 }}
            transition={{ duration: 1.1, delay: 0.15 + i * 0.22, ease: "easeOut" }}
          />
        ))}
        <motion.div
          className="grid size-24 place-items-center rounded-full bg-secondary text-secondary-ink shadow-[0_0_60px_-8px] shadow-secondary/70"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 380, damping: 18 }}
        >
          <motion.svg viewBox="0 0 24 24" className="size-11" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <motion.path
              d="M5 12.5l4.5 4.5L19 7.5"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.35, delay: 0.2, ease: "easeOut" }}
            />
          </motion.svg>
        </motion.div>
      </div>
      <motion.h1
        className="display mt-14 text-[38px] font-bold tracking-[0.06em]"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        Ready
      </motion.h1>
      <motion.p className="mt-2 text-fg-muted" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.45 }}>
        Everything&apos;s downloaded.
      </motion.p>
    </motion.div>
  );
}

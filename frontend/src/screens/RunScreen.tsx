import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, ArrowRight, Check, Cpu, FolderOpen, Gamepad2, Play, Square, X, Zap } from "lucide-react";
import { api, type Job, type ModelInfo, type RunSetup, type WorkerPlan } from "../bridge";
import { Button, Label, Modal, Panel, Stepper, Toggle } from "../components/ui";
import { ModelGate } from "./ModelGate";
import { PlayerNames } from "../components/PlayerNames";
import { CudaDialog } from "../components/CudaDialog";
import { cn } from "../lib/cn";
import { fmtBytes, fmtClock } from "../lib/format";
import { recordingLabel } from "../lib/recording";
import { useNow } from "../lib/useNow";
import { clips } from "../state/clips";
import { go } from "../state/nav";
import { gpu, run, shortGpu } from "../state/run";

export function RunScreen() {
  const running = run.use((s) => s.running);
  const finished = run.use((s) => s.finished);
  const [setupAgain, setSetupAgain] = useState(false);

  useEffect(() => {
    if (running) setSetupAgain(false);
  }, [running]);

  const live = running || (finished && !setupAgain);
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1240px] px-10 pb-10 pt-8">
        {live ? <LiveRun onNewRun={() => setSetupAgain(true)} /> : <Setup />}
      </div>
    </div>
  );
}

// ================================================================= setup

function Setup() {
  const videos = clips.use((s) => s.videos);
  const excluded = clips.use((s) => s.excluded);
  const selected = useMemo(() => videos.filter((v) => !excluded[v.path]), [videos, excluded]);
  const size = useMemo(() => selected.reduce((n, v) => n + v.size, 0), [selected]);

  const [setup, setSetup] = useState<RunSetup | null>(null);
  const [plan, setPlan] = useState<WorkerPlan | null>(null);
  const [workers, setWorkers] = useState<number | null>(null);
  const [gaming, setGaming] = useState(run.get().gaming);
  const [lowSpaceOpen, setLowSpaceOpen] = useState(false);
  const [cudaOpen, setCudaOpen] = useState(false);
  const [gate, setGate] = useState<ModelInfo[] | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api.run_setup().then((s) => {
      setSetup(s);
      setWorkers(s.workers);
    });
    void api.worker_plan().then(setPlan);
  }, []);

  const start = async (skipSpaceCheck = false) => {
    setError("");
    if (!skipSpaceCheck && setup?.low_space) return setLowSpaceOpen(true);
    setStarting(true);
    try {
      const r = await api.start_run(
        selected.map((v) => v.path),
        workers,
      );
      if (r.ok) return;
      if (r.error === "models_missing") {
        const status = await api.models_status();
        setGate(status.models);
      } else if (r.error === "no_videos") setError("None of the included recordings exist any more. Check the Clips screen.");
      else if (r.error === "running") setError("A run is already going.");
    } finally {
      setStarting(false);
    }
  };

  const dec = () => setWorkers((w) => Math.max(1, (w ?? plan?.workers ?? 1) - 1));
  const inc = () =>
    setWorkers((w) => {
      const current = w ?? plan?.workers ?? 1;
      // Past the plan's max they wouldn't fit in VRAM/RAM: back to auto.
      return plan && current >= plan.max_workers ? null : current + 1;
    });

  return (
    <>
      <div className="mb-7 flex items-end justify-between gap-6">
        <div>
          <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">Run</h1>
          <p className="mt-2 text-[15px] text-fg-muted">Check the setup, then start. Recordings already done are skipped.</p>
        </div>
        <LastRun />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Recordings" aside={<HeaderLink onClick={() => go("clips")}>Change selection</HeaderLink>}>
          <div className="flex items-baseline gap-3">
            <span className="display text-[44px] font-bold leading-none tabular">{selected.length}</span>
            <span className="text-[15px] text-fg-muted">
              of {videos.length} included · {fmtBytes(size)}
            </span>
          </div>
          {selected.length === 0 && (
            <p className="mt-3 text-[14px] text-warn">Nothing is included. Pick some recordings on the Clips screen.</p>
          )}
        </Panel>

        <Panel title="Your in-game name" aside={<span className="text-[13px] text-fg-faint">Optional</span>}>
          <RunNames initial={setup?.player_names} />
          <p className="mt-2.5 text-[13.5px] leading-relaxed text-fg-faint">
            CHAOS reads your name off the killfeed by itself. Add it here only if your kills get missed, or you play under more than one name.
          </p>
        </Panel>

        <Panel title="Clips folder">
          {setup ? (
            <>
              <div className="flex items-center gap-2.5 text-[15px]">
                <FolderOpen className="size-4 shrink-0 text-fg-faint" />
                <span className="truncate" title={setup.clips_folder}>
                  {setup.clips_folder}
                </span>
              </div>
              <div className={cn("mt-1.5 pl-[26px] text-[13.5px]", setup.low_space ? "font-semibold text-warn" : "text-fg-faint")}>
                {setup.free_bytes != null && `${fmtBytes(setup.free_bytes)} free`}
                {setup.low_space && ". Low on space, clips may fail to save."}
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" onClick={() => void api.choose_clips_folder().then(setSetup)}>
                  Change
                </Button>
                <Button size="sm" variant="ghost" onClick={() => void api.open_clips_folder()}>
                  Open
                </Button>
              </div>
            </>
          ) : (
            <div className="h-[92px] animate-pulse bg-white/[0.03]" />
          )}
        </Panel>

        <Panel title="Performance">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="font-medium">Analysis workers</div>
              <div className="mt-0.5 text-[13.5px] text-fg-faint">
                {plan ? (workers == null ? `Auto: ${plan.workers} fit right now` : `Up to ${plan.max_workers} fit right now`) : "Measuring…"}
              </div>
            </div>
            <Stepper value={workers ?? "Auto"} onDec={dec} onInc={inc} title={plan?.summary} />
          </div>
          <div className="my-4 h-px bg-line" />
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <Gamepad2 className="mt-0.5 size-5 text-fg-faint" />
              <div>
                <div className="font-medium">Gaming mode</div>
                <div className="mt-0.5 text-[13.5px] text-fg-faint">One worker at low priority, so your game stays smooth.</div>
              </div>
            </div>
            <Toggle
              on={gaming}
              label="Gaming mode"
              onChange={(on) => {
                setGaming(on);
                void api.set_gaming(on);
              }}
            />
          </div>
          <div className="my-4 h-px bg-line" />
          <GpuRow onEnable={() => setCudaOpen(true)} />
        </Panel>
      </div>

      <div className="mt-6 flex items-center justify-end gap-6">
        {error && <div className="mr-auto text-[14px] text-bad">{error}</div>}
        <div className="text-right text-[13.5px] text-fg-muted">
          <div className="display text-[16px] font-semibold text-fg">
            {selected.length} recording{selected.length === 1 ? "" : "s"}
          </div>
          {workers == null ? "Auto workers" : `${workers} worker${workers === 1 ? "" : "s"}`}
          {gaming && " · gaming mode"}
        </div>
        <Button variant="primary" size="lg" className="min-w-[220px]" disabled={!selected.length || starting} onClick={() => void start()}>
          <Play className="size-5 fill-current" /> {starting ? "Starting" : "Start"}
        </Button>
      </div>

      <LowSpaceDialog
        open={lowSpaceOpen}
        setup={setup}
        onClose={() => setLowSpaceOpen(false)}
        onChange={() => void api.choose_clips_folder().then((s) => {
          setSetup(s);
          setLowSpaceOpen(s.low_space);
        })}
        onRunAnyway={() => {
          setLowSpaceOpen(false);
          void start(true);
        }}
      />
      <CudaDialog open={cudaOpen} onClose={() => setCudaOpen(false)} />
      <AnimatePresence>
        {gate && (
          <motion.div className="fixed inset-0 z-50 bg-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <ModelGate
              models={gate}
              onReady={() => {
                setGate(null);
                void start(true);
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function HeaderLink({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className="display flex items-center gap-1 text-[13px] font-semibold tracking-[0.1em] text-fg-faint transition hover:text-accent">
      {children} <ArrowRight className="size-3.5" />
    </button>
  );
}

function LastRun() {
  const finished = run.use((s) => s.finished);
  if (!finished) return null;
  return (
    <div className="text-right text-[13.5px] text-fg-faint">
      Last run: {finished.success ? `${finished.clips} clip${finished.clips === 1 ? "" : "s"} in ${fmtClock(finished.elapsed)}` : `stopped after ${fmtClock(finished.elapsed)}`}
    </div>
  );
}

function RunNames({ initial }: { initial?: string[] }) {
  const [names, setNames] = useState<string[]>([]);
  useEffect(() => {
    if (initial) setNames(initial);
  }, [initial]);
  return (
    <PlayerNames
      value={names}
      onChange={(next) => {
        setNames(next);
        void api.save_player_names(next);
      }}
    />
  );
}

function GpuRow({ onEnable }: { onEnable: () => void }) {
  const info = gpu.use((s) => s.info);
  if (!info) return <div className="h-10 animate-pulse bg-white/[0.03]" />;
  if (info.cuda_available)
    return (
      <div className="flex items-center gap-3">
        <Zap className="size-5 text-secondary-hi" />
        <div>
          <div className="font-medium">{shortGpu(info.gpu_name)}</div>
          <div className="text-[13.5px] text-secondary-hi">GPU acceleration on</div>
        </div>
      </div>
    );
  if (info.gpu_present)
    return (
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Zap className="size-5 text-warn" />
          <div>
            <div className="font-medium">{shortGpu(info.gpu_name)}</div>
            <div className="text-[13.5px] text-warn">Not being used. Up to 8x faster with it on.</div>
          </div>
        </div>
        <Button size="sm" variant="primary" onClick={onEnable}>
          Turn on
        </Button>
      </div>
    );
  return (
    <div className="flex items-center gap-3">
      <Cpu className="size-5 text-fg-faint" />
      <div>
        <div className="font-medium">CPU only</div>
        <div className="text-[13.5px] text-fg-faint">No NVIDIA GPU found, so analysis runs on the processor.</div>
      </div>
    </div>
  );
}

function LowSpaceDialog({
  open,
  setup,
  onClose,
  onChange,
  onRunAnyway,
}: {
  open: boolean;
  setup: RunSetup | null;
  onClose: () => void;
  onChange: () => void;
  onRunAnyway: () => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Low disk space" width={500}>
      <div className="flex gap-3.5">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" />
        <div className="text-[15px] leading-relaxed text-fg-muted">
          Only <span className="font-semibold text-fg">{setup?.free_bytes != null ? fmtBytes(setup.free_bytes) : "a little"}</span> free
          on the drive for <span className="break-all text-fg">{setup?.clips_folder}</span>. Clips may fail to save if it fills up.
        </div>
      </div>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={onRunAnyway}>Run anyway</Button>
        <Button variant="primary" onClick={onChange}>
          Change folder
        </Button>
      </div>
    </Modal>
  );
}

// ================================================================= live run

const STAGES: { id: Job["stage"]; label: string }[] = [
  { id: "analyze", label: "Analyze" },
  { id: "correlate", label: "Find clips" },
  { id: "clip", label: "Cut" },
];
const STAGE_INDEX: Record<Job["stage"], number> = { queued: -1, analyze: 0, correlate: 1, clip: 2, done: 3, failed: 3 };

function LiveRun({ onNewRun }: { onNewRun: () => void }) {
  const running = run.use((s) => s.running);
  const jobs = run.use((s) => s.jobs);
  const order = run.use((s) => s.order);

  const groups = useMemo(() => {
    const working: Job[] = [];
    const queued: Job[] = [];
    const finished: Job[] = [];
    for (const name of order) {
      const j = jobs[name];
      if (!j) continue;
      if (j.stage === "queued") queued.push(j);
      else if (j.stage === "done" || j.stage === "failed") finished.push(j);
      else working.push(j);
    }
    return { working, queued, finished };
  }, [jobs, order]);

  return (
    <>
      {running ? <RunHeader /> : <FinishedBanner onNewRun={onNewRun} />}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_440px]">
        <div className="flex min-w-0 flex-col gap-4">
          {groups.working.length > 0 && (
            <Panel title={`Working on · ${groups.working.length}`} bodyClassName="p-0">
              <AnimatePresence initial={false}>
                {groups.working.map((j) => (
                  <JobRow key={j.name} job={j} />
                ))}
              </AnimatePresence>
            </Panel>
          )}
          {groups.queued.length > 0 && (
            <Panel title={`Up next · ${groups.queued.length}`} bodyClassName="py-3">
              <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-[14px] text-fg-muted">
                {groups.queued.slice(0, 12).map((j) => (
                  <span key={j.name}>{recordingLabel(j.name)}</span>
                ))}
                {groups.queued.length > 12 && <span className="text-fg-faint">and {groups.queued.length - 12} more</span>}
              </div>
            </Panel>
          )}
          {groups.finished.length > 0 && (
            <Panel title={`Finished · ${groups.finished.length}`} bodyClassName="p-0">
              {groups.finished.slice(0, 60).map((j) => (
                <JobRow key={j.name} job={j} />
              ))}
              {groups.finished.length > 60 && (
                <div className="px-4 py-2.5 text-[13.5px] text-fg-faint">and {groups.finished.length - 60} more</div>
              )}
            </Panel>
          )}
          {order.length === 0 && (
            <Panel bodyClassName="py-10 text-center text-fg-faint">
              <span className="display animate-pulse tracking-[0.12em]">Getting ready</span>
            </Panel>
          )}
        </div>
        <LogPanel />
      </div>
    </>
  );
}

function RunHeader() {
  const done = run.use((s) => s.done);
  const total = run.use((s) => s.total);
  const startedAt = run.use((s) => s.started_at);
  const workers = run.use((s) => s.workers);
  const gaming = run.use((s) => s.gaming);
  const last = run.use((s) => s.log[s.log.length - 1]?.text);
  const [stopping, setStopping] = useState(false);
  const now = useNow();
  const elapsed = startedAt ? now - startedAt : 0;
  const eta = done > 0 && total > done ? (elapsed / done) * (total - done) : null;
  const pct = total ? (done / total) * 100 : 0;

  return (
    <section className="relative overflow-hidden border border-accent/30 bg-panel/80 backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-x-10 gap-y-4 px-6 pb-5 pt-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="size-2.5 animate-pulse rounded-full bg-accent shadow-[0_0_10px] shadow-accent" />
            <span className="display text-[15px] font-semibold tracking-[0.14em] text-accent">{stopping ? "Stopping" : "Analyzing"}</span>
          </div>
          <div className="display mt-1 text-[52px] font-bold leading-none tabular">
            {done}
            <span className="text-[30px] text-fg-faint"> / {total}</span>
          </div>
        </div>
        <Stat label="Elapsed" value={fmtClock(elapsed)} />
        <Stat label="Time left" value={eta != null ? `~${fmtClock(eta)}` : "…"} />
        <div className="ml-auto flex flex-wrap items-center gap-5">
          <div>
            <Label className="mb-1.5">Workers</Label>
            <Stepper
              value={gaming ? 1 : (workers ?? "…")}
              onDec={() => workers && void api.set_run_workers(Math.max(1, workers - 1))}
              onInc={() => workers && void api.set_run_workers(workers + 1)}
            />
          </div>
          <div>
            <Label className="mb-1.5">Gaming mode</Label>
            <div className="flex h-8 items-center">
              <Toggle on={gaming} label="Gaming mode" onChange={(on) => void api.set_gaming(on)} />
            </div>
          </div>
          <Button
            variant="danger"
            className="self-end"
            disabled={stopping}
            onClick={() => {
              setStopping(true);
              void api.stop_run();
            }}
          >
            <Square className="size-3.5 fill-current" /> Stop
          </Button>
        </div>
      </div>
      <div className="truncate px-6 pb-3 text-[13.5px] text-fg-faint">{last ?? "Starting…"}</div>
      <div className="relative h-1.5 bg-black/40">
        <motion.div className="relative h-full overflow-hidden bg-accent" animate={{ width: `${pct}%` }} transition={{ type: "spring", stiffness: 60, damping: 20 }}>
          <span className="stripes absolute inset-0" />
        </motion.div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="display mt-1 text-[28px] font-semibold leading-none tabular">{value}</div>
    </div>
  );
}

function FinishedBanner({ onNewRun }: { onNewRun: () => void }) {
  const finished = run.use((s) => s.finished)!;
  const total = run.use((s) => s.order.length);
  const ok = finished.success;
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex flex-wrap items-center gap-6 border bg-panel/80 px-6 py-5 backdrop-blur-xl", ok ? "border-secondary/50" : "border-bad/40")}
    >
      <motion.div
        initial={{ scale: 0.4 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 400, damping: 18 }}
        className={cn("grid size-14 place-items-center", ok ? "bg-secondary text-secondary-ink shadow-[0_0_30px_-4px] shadow-secondary" : "bg-bad/20 text-bad")}
      >
        {ok ? <Check className="size-8" strokeWidth={3} /> : <X className="size-8" strokeWidth={3} />}
      </motion.div>
      <div>
        <div className={cn("display text-[30px] font-bold leading-none tracking-[0.05em]", ok ? "text-fg" : "text-bad")}>
          {ok ? "Run complete" : "Run stopped"}
        </div>
        <div className="mt-1.5 text-[15px] text-fg-muted">
          {ok
            ? `${finished.clips} clip${finished.clips === 1 ? "" : "s"} from ${total} recording${total === 1 ? "" : "s"} in ${fmtClock(finished.elapsed)}.`
            : `Stopped after ${fmtClock(finished.elapsed)}. The log says why.`}
        </div>
      </div>
      <div className="ml-auto flex gap-2">
        <Button variant="ghost" onClick={onNewRun}>
          New run
        </Button>
        <Button onClick={() => void api.open_clips_folder()}>Open clips folder</Button>
        {ok && finished.clips > 0 && (
          <Button variant="primary" onClick={() => go("highlights")}>
            See highlights <ArrowRight className="size-4" />
          </Button>
        )}
      </div>
    </motion.section>
  );
}

function JobRow({ job }: { job: Job }) {
  const at = STAGE_INDEX[job.stage];
  if (job.stage === "done" || job.stage === "failed") return <FinishedRow job={job} />;
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-4 border-b border-line px-4 py-2.5 last:border-b-0"
    >
      <div className="w-[170px] shrink-0 truncate text-[14.5px]" title={job.name}>
        {recordingLabel(job.name)}
      </div>
      <div className="flex min-w-0 flex-1 gap-1">
        {STAGES.map((s, i) => {
          const state = i < at ? "done" : i === at ? "active" : "todo";
          return (
            <div key={s.id} className="min-w-0 flex-1">
              <div
                className={cn(
                  "relative h-1.5 overflow-hidden",
                  state === "done" && "bg-secondary",
                  state === "active" && "bg-accent",
                  state === "todo" && "bg-white/[0.08]",
                )}
              >
                {state === "active" && <span className="stripes absolute inset-0" />}
              </div>
              <div
                className={cn(
                  "display mt-1 truncate text-[11.5px] font-semibold tracking-[0.1em]",
                  state === "active" ? "text-accent" : state === "done" ? "text-secondary-hi/80" : "text-fg-faint",
                )}
              >
                {s.label}
              </div>
            </div>
          );
        })}
      </div>
      <div className="w-[72px] shrink-0 text-right text-[14px] tabular">
        {job.clips != null && (
          <span className={job.clips ? "font-semibold text-secondary-hi" : "text-fg-faint"}>
            {job.clips} clip{job.clips === 1 ? "" : "s"}
          </span>
        )}
      </div>
    </motion.div>
  );
}

function FinishedRow({ job }: { job: Job }) {
  const ok = job.stage === "done";
  return (
    <div className="flex items-center gap-3 border-b border-line px-4 py-2 last:border-b-0">
      <span className={cn("grid size-5 place-items-center", ok ? "bg-secondary/30 text-secondary-hi" : "bg-bad/20 text-bad")}>
        {ok ? <Check className="size-3.5" strokeWidth={3} /> : <X className="size-3.5" strokeWidth={3} />}
      </span>
      <div className="min-w-0 flex-1 truncate text-[14.5px] text-fg-muted" title={job.name}>
        {recordingLabel(job.name)}
      </div>
      <div className="text-[14px] tabular">
        {!ok ? (
          <span className="text-bad">Failed</span>
        ) : job.clips ? (
          <span className="font-semibold text-secondary-hi">
            {job.clips} clip{job.clips === 1 ? "" : "s"}
          </span>
        ) : (
          <span className="text-fg-faint">No clips</span>
        )}
      </div>
    </div>
  );
}

function LogPanel() {
  const log = run.use((s) => s.log);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [follow, setFollow] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const shown = useMemo(() => (errorsOnly ? log.filter((l) => l.level === "error") : log).slice(-800), [log, errorsOnly]);
  const errors = useMemo(() => log.filter((l) => l.level === "error").length, [log]);

  useEffect(() => {
    if (follow) box.current?.scrollTo(0, box.current.scrollHeight);
  }, [shown, follow]);

  const exportLog = () =>
    void api.export_log(log.map((l) => `${new Date(l.t * 1000).toLocaleTimeString()}  ${l.level === "error" ? "ERROR " : ""}${l.text}`).join("\n"));

  return (
    <Panel
      title="Log"
      className="flex h-[min(640px,calc(100vh-260px))] min-h-[320px] flex-col"
      bodyClassName="flex min-h-0 flex-1 flex-col p-0"
      aside={
        <div className="flex items-center gap-1">
          <button
            onClick={() => setErrorsOnly((e) => !e)}
            className={cn(
              "display px-2 py-1 text-[12.5px] font-semibold tracking-[0.08em] transition",
              errorsOnly ? "bg-bad/15 text-bad" : "text-fg-faint hover:text-fg",
            )}
          >
            Errors{errors ? ` · ${errors}` : ""}
          </button>
          <button onClick={exportLog} className="display px-2 py-1 text-[12.5px] font-semibold tracking-[0.08em] text-fg-faint transition hover:text-fg">
            Export
          </button>
        </div>
      }
    >
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget;
          setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 24);
        }}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-3 font-mono text-[12px] leading-[1.7] select-text"
      >
        {shown.length === 0 && <div className="text-fg-faint">{errorsOnly ? "No errors." : "Nothing yet."}</div>}
        {shown.map((l, i) => (
          <div key={i} className={cn("break-words", l.level === "error" ? "text-bad" : "text-fg-muted")}>
            <span className="mr-2 text-fg-faint">{new Date(l.t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
            {l.text}
          </div>
        ))}
      </div>
    </Panel>
  );
}

import { useEffect, useState, type ComponentType } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Clapperboard, Film, Play, Settings, Sparkles, type LucideProps } from "lucide-react";
import { Wordmark } from "./Wordmark";
import { Room } from "./Room";
import { cn } from "../lib/cn";
import { fmtClock } from "../lib/format";
import { loadClips } from "../state/clips";
import { gpu, loadGpu, run, shortGpu, syncRun } from "../state/run";
import { go, nav, setPeek, type ScreenId } from "../state/nav";
import { loadPrefs, prefs } from "../state/prefs";
import { SettingsScreen } from "../screens/SettingsScreen";
import { HighlightsScreen } from "../screens/HighlightsScreen";
import { WatchScreen } from "../screens/WatchScreen";
import { SetupWizard } from "../screens/SetupWizard";
import { api } from "../bridge";
import { ClipsScreen } from "../screens/ClipsScreen";
import { RunScreen } from "../screens/RunScreen";

interface NavItem {
  id: ScreenId;
  label: string;
  icon: ComponentType<LucideProps>;
  blurb: string;
}

const NAV: NavItem[] = [
  { id: "clips", label: "Clips", icon: Film, blurb: "Pick the recordings to scan for highlights." },
  { id: "run", label: "Run", icon: Play, blurb: "Watch CHAOS work through your recordings live." },
  { id: "highlights", label: "Highlights", icon: Sparkles, blurb: "Your best moments, ranked, with every kill and laugh marked." },
  { id: "watch", label: "Watch", icon: Clapperboard, blurb: "Play your highlights back to back and export them as one video." },
];
const SETTINGS: NavItem = { id: "settings", label: "Settings", icon: Settings, blurb: "Folders, detection tuning and models." };

export function Shell() {
  const screen = nav.use((s) => s.screen);
  const peek = nav.use((s) => s.peek);
  const background = prefs.use((s) => s.background);
  const motion_ = prefs.use((s) => s.background_motion);
  const loaded = prefs.use((s) => s.loaded);
  const [setup, setSetup] = useState(false);

  useEffect(() => {
    void loadPrefs();
    void loadClips();
    void api.system_check().then((c) => setSetup(!c.setup_complete));
    void syncRun();
    void loadGpu();
  }, []);

  useEffect(() => {
    if (!peek) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPeek(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [peek]);

  return (
    <div className="relative h-full">
      {loaded && background ? (
        <Room mode={peek ? "room" : "screen"} still={!motion_} onPick={go} />
      ) : (
        <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_50%_0%,#151b23,var(--color-bg)_70%)]" />
      )}
      <AnimatePresence>
        {setup && (
          <motion.div key="setup" exit={{ opacity: 0, transition: { duration: 0.3 } }}>
            <SetupWizard onDone={() => setSetup(false)} />
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {peek ? (
          <motion.button
            key="back"
            onClick={() => setPeek(false)}
            className="display absolute bottom-6 left-1/2 -translate-x-1/2 text-[13px] font-semibold tracking-[0.2em] text-white/40 transition hover:text-white/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 1.2 } }}
            exit={{ opacity: 0 }}
          >
            Esc to get back
          </motion.button>
        ) : (
          <motion.div
            key="app"
            className="relative flex h-full flex-col"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } }}
            exit={{ opacity: 0, scale: 1.02, transition: { duration: 0.35 } }}
          >
            <TopBar screen={screen} />
            <main className="relative min-h-0 flex-1">
              <AnimatePresence mode="wait">
                <motion.section
                  key={screen}
                  className="absolute inset-0"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] } }}
                  exit={{ opacity: 0, transition: { duration: 0.1 } }}
                >
                  {screen === "clips" ? (
                    <ClipsScreen />
                  ) : screen === "run" ? (
                    <RunScreen />
                  ) : screen === "highlights" ? (
                    <HighlightsScreen />
                  ) : screen === "watch" ? (
                    <WatchScreen />
                  ) : screen === "settings" ? (
                    <SettingsScreen />
                  ) : (
                    <ComingSoon item={[...NAV, SETTINGS].find((n) => n.id === screen)!} />
                  )}
                </motion.section>
              </AnimatePresence>
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Five quick clicks on the gear bring the room behind the app into focus.
let gearClicks: number[] = [];

function onSettings() {
  const now = Date.now();
  gearClicks = [...gearClicks.filter((t) => now - t < 2500), now];
  if (gearClicks.length >= 5 && prefs.get().background) {
    gearClicks = [];
    setPeek(true);
  } else go("settings");
}

function TopBar({ screen }: { screen: ScreenId }) {
  return (
    <header className="relative z-10 flex h-16 shrink-0 items-stretch border-b border-line bg-gradient-to-b from-black/55 to-black/25 pr-3 backdrop-blur-md">
      <button onClick={() => go("clips")} className="flex items-center px-5" aria-label="CHAOS">
        <Wordmark className="h-9" />
      </button>
      <nav className="flex items-stretch">
        {NAV.map((item) => (
          <Tab key={item.id} item={item} active={screen === item.id} />
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        <RunPill />
        <GpuChip />
        <button
          onClick={onSettings}
          className={cn(
            "grid size-10 place-items-center transition hover:bg-white/[0.07]",
            screen === "settings" ? "text-accent" : "text-fg-muted hover:text-fg",
          )}
          aria-label="Settings"
          title="Settings"
        >
          <Settings className="size-5" />
        </button>
      </div>
    </header>
  );
}

function Tab({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <button
      onClick={() => go(item.id)}
      className={cn(
        "display relative flex items-center px-5 text-[17px] font-semibold tracking-[0.09em] transition-colors",
        active ? "text-fg" : "text-fg-muted hover:text-fg",
      )}
    >
      {active && (
        <motion.span
          layoutId="tab-active"
          className="absolute inset-0 bg-gradient-to-t from-accent/20 to-transparent"
          transition={{ type: "spring", stiffness: 500, damping: 40 }}
        >
          <span className="absolute inset-x-0 bottom-0 h-[3px] bg-accent shadow-[0_0_12px] shadow-accent" />
        </motion.span>
      )}
      <span className="relative">{item.label}</span>
    </button>
  );
}

/** While a run is going, a CS2 "searching" style pill in the top bar. */
function RunPill() {
  const running = run.use((s) => s.running);
  const done = run.use((s) => s.done);
  const total = run.use((s) => s.total);
  const startedAt = run.use((s) => s.started_at);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [running]);
  return (
    <AnimatePresence>
      {running && (
        <motion.button
          onClick={() => go("run")}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className="display relative flex h-10 items-center gap-3 overflow-hidden border border-accent/50 bg-accent/10 px-4 text-[15px] font-semibold"
        >
          <span className="stripes absolute inset-0 opacity-30" />
          <span className="relative size-2 animate-pulse rounded-full bg-accent" />
          <span className="relative">Analyzing</span>
          <span className="relative tabular text-fg-muted">
            {done}/{total}
          </span>
          <span className="relative tabular text-fg-muted">{startedAt ? fmtClock(now - startedAt) : ""}</span>
        </motion.button>
      )}
    </AnimatePresence>
  );
}

function GpuChip() {
  const info = gpu.use((s) => s.info);
  let dot = "bg-fg-faint";
  let title = "Checking";
  if (info) {
    if (info.cuda_available) {
      dot = "bg-secondary-hi";
      title = shortGpu(info.gpu_name);
    } else if (info.gpu_present) {
      dot = "bg-warn";
      title = `${shortGpu(info.gpu_name)} · GPU off`;
    } else title = "CPU only";
  }
  return (
    <button
      onClick={() => go("run")}
      title={
        info?.cuda_available
          ? "GPU acceleration is on"
          : info?.gpu_present
            ? "GPU acceleration is off. Turn it on from the Run screen."
            : undefined
      }
      className="display flex h-10 items-center gap-2.5 px-3 text-[14px] font-semibold text-fg-muted transition hover:bg-white/[0.06] hover:text-fg"
    >
      <span className="relative flex size-2">
        {(!info || info.checking) && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60", dot)} />}
        <span className={cn("relative size-2 rounded-full", dot)} />
      </span>
      {title}
    </button>
  );
}

/** Placeholder until a screen is ported (see REACT_FRONTEND_PLAN.md). */
function ComingSoon({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <div className="flex h-full flex-col px-10 pb-10 pt-8">
      <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">{item.label}</h1>
      <p className="mt-2 text-[15px] text-fg-muted">{item.blurb}</p>
      <div className="mt-8 grid flex-1 place-items-center border border-dashed border-line-strong bg-panel/40 backdrop-blur-sm">
        <div className="flex max-w-[360px] flex-col items-center text-center">
          <div className="grid size-12 place-items-center border border-line bg-raised">
            <Icon className="size-5 text-fg-muted" />
          </div>
          <div className="display mt-4 text-[17px] font-semibold">Not in the new app yet</div>
          <p className="mt-1.5 text-[14px] leading-relaxed text-fg-faint">
            This screen is still being rebuilt. Until then it&apos;s in the classic app: run{" "}
            <code className="font-mono text-[12.5px] text-fg-muted">run_desktop_app.py</code> without{" "}
            <code className="font-mono text-[12.5px] text-fg-muted">--web</code>.
          </p>
        </div>
      </div>
    </div>
  );
}

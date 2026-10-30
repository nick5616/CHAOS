import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, Check, FolderOpen, Loader2, X } from "lucide-react";
import { api, type SystemCheck } from "../bridge";
import { Backdrop } from "../components/Backdrop";
import { Button } from "../components/ui";
import { CudaDialog } from "../components/CudaDialog";
import { PlayerNames } from "../components/PlayerNames";
import { RegionEditor, RegionPreview, presetFor } from "../components/RegionEditor";
import { Wordmark } from "../components/Wordmark";
import { cn } from "../lib/cn";
import { clips, loadClips } from "../state/clips";
import { gpu, shortGpu } from "../state/run";
import { apply, loadSettings, setSetting, setSettings, settings } from "../state/settings";

const STEPS = ["Check", "Recordings", "Name", "Killfeed"];

/** First launch: check the machine, then the few settings CHAOS needs. */
export function SetupWizard({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const bundle = settings.use((s) => s.bundle);
  const [check, setCheck] = useState<SystemCheck | null>(null);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    void loadSettings();
    void api.system_check().then(setCheck);
  }, []);

  const folder = bundle?.values.captures_folder ?? "";
  useEffect(() => {
    if (folder) void api.list_clips().then((l) => setCount(l.exists ? l.videos.length : null));
  }, [folder]);

  const canContinue = step === 0 ? !!check?.ffmpeg.ok : step === 1 ? !!folder && count != null && count > 0 : true;

  const finish = () => {
    setSetting("gui.setup_complete", true, 0);
    void loadClips(true);
    onDone();
  };

  return (
    <div className="fixed inset-0 z-40 overflow-hidden bg-bg">
      <Backdrop />
      <div className="relative z-10 flex h-full flex-col items-center overflow-y-auto px-6 py-10">
        <div className="w-full max-w-[640px]">
          <div className="flex items-center justify-between">
            <Wordmark className="h-12" />
            <div className="flex items-center gap-2">
              {STEPS.map((s, i) => (
                <div key={s} className="flex items-center gap-2">
                  <span
                    className={cn(
                      "display grid size-7 place-items-center border text-[13px] font-bold",
                      i < step ? "border-secondary bg-secondary text-secondary-ink" : i === step ? "border-accent text-accent" : "border-line-strong text-fg-faint",
                    )}
                  >
                    {i < step ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
                  </span>
                  {i < STEPS.length - 1 && <span className={cn("h-px w-5", i < step ? "bg-secondary" : "bg-line-strong")} />}
                </div>
              ))}
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] } }}
              exit={{ opacity: 0, x: -24, transition: { duration: 0.15 } }}
              className="mt-10"
            >
              {step === 0 && <StepCheck check={check} />}
              {step === 1 && <StepFolder folder={folder} count={count} />}
              {step === 2 && bundle && <StepName names={bundle.values.player_names} />}
              {step === 3 && bundle && <StepRegion />}
            </motion.div>
          </AnimatePresence>

          <div className="mt-10 flex items-center justify-between">
            {step > 0 ? (
              <Button variant="ghost" onClick={() => setStep(step - 1)}>
                <ArrowLeft className="size-4" /> Back
              </Button>
            ) : (
              <span />
            )}
            {step < STEPS.length - 1 ? (
              <Button variant="primary" size="lg" disabled={!canContinue} onClick={() => setStep(step + 1)}>
                {step === 2 && !bundle?.values.player_names.length ? "Skip" : "Continue"} <ArrowRight className="size-5" />
              </Button>
            ) : (
              <Button variant="primary" size="lg" onClick={finish}>
                Start using CHAOS <ArrowRight className="size-5" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Heading({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <h1 className="display text-[38px] font-bold leading-none tracking-[0.04em]">{title}</h1>
      <p className="mt-3 text-[15.5px] leading-relaxed text-fg-muted">{children}</p>
    </>
  );
}

function CheckRow({ label, state, detail, action }: { label: string; state: "ok" | "bad" | "warn" | "wait"; detail: string; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-4 border-b border-line px-4 py-3.5 last:border-b-0">
      <span
        className={cn(
          "grid size-6 shrink-0 place-items-center",
          state === "ok" && "bg-secondary/30 text-secondary-hi",
          state === "bad" && "bg-bad/20 text-bad",
          state === "warn" && "bg-warn/20 text-warn",
        )}
      >
        {state === "wait" ? <Loader2 className="size-4 animate-spin text-fg-faint" /> : state === "bad" ? <X className="size-3.5" strokeWidth={3} /> : <Check className="size-3.5" strokeWidth={3} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-medium">{label}</div>
        <div className="truncate text-[13.5px] text-fg-faint">{detail}</div>
      </div>
      {action}
    </div>
  );
}

function StepCheck({ check }: { check: SystemCheck | null }) {
  const info = gpu.use((s) => s.info);
  const [cuda, setCuda] = useState(false);
  const gpuState = !info || info.checking ? "wait" : info.cuda_available ? "ok" : "warn";
  return (
    <>
      <Heading title="Welcome to CHAOS">
        CHAOS finds the best moments in your CS2 recordings: kills, clutches and the funny stuff on voice chat. First, a quick check of this
        PC.
      </Heading>
      <div className="mt-7 border border-line bg-panel/75 backdrop-blur-xl">
        <CheckRow label="Python" state={!check ? "wait" : check.python.ok ? "ok" : "bad"} detail={check ? `Version ${check.python.detail}` : "Checking…"} />
        <CheckRow
          label="FFmpeg"
          state={!check ? "wait" : check.ffmpeg.ok ? "ok" : "bad"}
          detail={!check ? "Checking…" : check.ffmpeg.ok ? check.ffmpeg.detail : "Not found. Run setup.bat again to install it."}
        />
        <CheckRow
          label="Graphics card"
          state={gpuState}
          detail={
            !info || info.checking
              ? "Checking…"
              : info.cuda_available
                ? `${shortGpu(info.gpu_name)}, GPU acceleration on`
                : info.gpu_present
                  ? `${shortGpu(info.gpu_name)} found but not used. Up to 8x faster with it on.`
                  : "No NVIDIA GPU, so analysis runs on the processor. That works, just slower."
          }
          action={
            info && !info.cuda_available && info.gpu_present ? (
              <Button size="sm" variant="primary" onClick={() => setCuda(true)}>
                Turn on
              </Button>
            ) : undefined
          }
        />
      </div>
      <CudaDialog open={cuda} onClose={() => setCuda(false)} />
    </>
  );
}

function StepFolder({ folder, count }: { folder: string; count: number | null }) {
  return (
    <>
      <Heading title="Where are your recordings?">
        Point CHAOS at the folder your recorder (ShadowPlay, OBS...) saves CS2 videos to. Nothing in it is changed or moved.
      </Heading>
      <div className="mt-7 flex items-center gap-3 border border-line bg-panel/75 px-4 py-4 backdrop-blur-xl">
        <FolderOpen className="size-5 shrink-0 text-fg-faint" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px]">{folder || <span className="text-fg-faint">No folder chosen</span>}</div>
          {folder && (
            <div className={cn("mt-0.5 text-[13.5px]", count ? "text-secondary-hi" : "text-warn")}>
              {count == null ? "That folder doesn't exist." : count ? `Found ${count} recording${count === 1 ? "" : "s"}` : "No videos in this folder."}
            </div>
          )}
        </div>
        <Button variant={folder ? "secondary" : "primary"} onClick={async () => apply(await api.choose_setting_folder("captures_folder"))}>
          {folder ? "Change" : "Choose folder"}
        </Button>
      </div>
    </>
  );
}

function StepName({ names }: { names: string[] }) {
  return (
    <>
      <Heading title="What's your in-game name?">
        Optional. CHAOS reads your name off the killfeed by itself; add it if you want to be sure, or if you play under more than one.
      </Heading>
      <div className="mt-7 border border-line bg-panel/75 p-4 backdrop-blur-xl">
        <PlayerNames value={names} onChange={(n) => setSetting("player_names", n, 0)} />
      </div>
    </>
  );
}

function StepRegion() {
  const values = settings.use((s) => s.bundle!.values);
  const [detected, setDetected] = useState<[number, number] | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const newest = clips.use((s) => s.videos[0]?.name);

  // Start from the preset for the newest recording's resolution.
  useEffect(() => {
    void api.detect_resolution().then((res) => {
      setDetected(res);
      // Only when the saved region was made for another resolution, so
      // stepping back and forth doesn't undo an adjustment.
      const saved = settings.get().bundle?.values.killfeed_roi_resolution;
      if (res && (!saved || saved[0] !== res[0] || saved[1] !== res[1]))
        setSettings({ killfeed_roi: presetFor(res), killfeed_roi_resolution: res });
    });
  }, [newest]);

  return (
    <>
      <Heading title="Find the killfeed">
        {detected
          ? `Your newest recording is ${detected[0]}×${detected[1]}, so CHAOS picked the matching region. Check the box sits over the killfeed (top right); click it to adjust.`
          : detected === null
            ? "CHAOS couldn't read your recordings' resolution. Click the frame to place the box over the killfeed."
            : "Reading your newest recording…"}
      </Heading>
      <div className="mt-7">
        <RegionPreview key={`${values.killfeed_roi.join()}`} roi={values.killfeed_roi} resolution={values.killfeed_roi_resolution} onEdit={() => setEditing(true)} />
      </div>
      <RegionEditor
        open={editing}
        roi={values.killfeed_roi}
        resolution={values.killfeed_roi_resolution}
        onClose={() => setEditing(false)}
        onSave={(roi, res) => {
          setSettings({ killfeed_roi: roi, killfeed_roi_resolution: res });
          setEditing(false);
        }}
      />
    </>
  );
}

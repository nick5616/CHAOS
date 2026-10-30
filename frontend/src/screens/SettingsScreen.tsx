import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, Check, Download, FolderOpen, Monitor, MoveHorizontal, RotateCcw } from "lucide-react";
import { api, type Hsv, type ModelInfo, type SettingsValues } from "../bridge";
import { Button, Label, Modal, Panel, Toggle } from "../components/ui";
import { PlayerNames } from "../components/PlayerNames";
import { RangeSlider, Slider } from "../components/Slider";
import { RegionEditor, RegionPreview } from "../components/RegionEditor";
import { ModelGate } from "./ModelGate";
import { cn } from "../lib/cn";
import { fmtSize } from "../lib/format";
import { prefs, setPref } from "../state/prefs";
import { apply, loadSettings, setSetting, setSettings, settings } from "../state/settings";
import { loadClips } from "../state/clips";

type Tab = "general" | "detection" | "appearance";
const TABS: { id: Tab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "detection", label: "Detection" },
  { id: "appearance", label: "Appearance" },
];

export function SettingsScreen() {
  const bundle = settings.use((s) => s.bundle);
  const [tab, setTab] = useState<Tab>("general");

  useEffect(() => {
    void loadSettings();
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="mx-auto w-full max-w-[920px] px-10 pt-8">
        <div className="flex items-end justify-between gap-6">
          <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">Settings</h1>
          <SaveState />
        </div>
        <div className="mt-6 flex border-b border-line">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "display relative px-5 pb-3 pt-1 text-[16px] font-semibold tracking-[0.1em] transition-colors",
                tab === t.id ? "text-fg" : "text-fg-faint hover:text-fg",
              )}
            >
              {t.label}
              {tab === t.id && <motion.span layoutId="settings-tab" className="absolute inset-x-2 -bottom-px h-[3px] bg-accent" />}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[920px] px-10 pb-12 pt-6">
          {!bundle ? (
            <div className="display animate-pulse py-20 text-center tracking-[0.12em] text-fg-faint">Loading</div>
          ) : tab === "general" ? (
            <General values={bundle.values} resolved={bundle.resolved} />
          ) : tab === "detection" ? (
            <Detection values={bundle.values} defaults={bundle.defaults} />
          ) : (
            <Appearance />
          )}
        </div>
      </div>
    </div>
  );
}

function SaveState() {
  const saving = settings.use((s) => s.saving);
  const savedAt = settings.use((s) => s.savedAt);
  const error = settings.use((s) => s.error);
  return (
    // No AnimatePresence here: with "wait", quick successive saves left a
    // stale "Saving…" on screen. Each state just fades in on mount.
    <div className="h-6 text-[13.5px]">
      {error ? (
          <motion.span key="e" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-1.5 text-bad">
            <AlertTriangle className="size-4" /> {error}
          </motion.span>
        ) : saving ? (
          <motion.span key="s" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-fg-faint">
            Saving…
          </motion.span>
        ) : savedAt ? (
          <motion.span key={savedAt} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-1.5 text-secondary-hi">
            <Check className="size-4" /> Saved
          </motion.span>
        ) : (
          <span className="text-fg-faint">Changes save automatically</span>
        )}
    </div>
  );
}

function Row({ title, detail, children, className }: { title: ReactNode; detail?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-6 border-b border-line px-4 py-3.5 last:border-b-0", className)}>
      <div className="min-w-0 flex-1">
        <div className="font-medium">{title}</div>
        {detail && <div className="mt-0.5 text-[13.5px] leading-relaxed text-fg-faint">{detail}</div>}
      </div>
      {children}
    </div>
  );
}

// ================================================================= general

function General({ values, resolved }: { values: SettingsValues; resolved: { data_folder: string; final_clips_folder: string } }) {
  const [editing, setEditing] = useState(false);
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [gate, setGate] = useState<ModelInfo[] | null>(null);
  const voiceKey = `${values["moments.mode"]}|${values["subtitles.enabled"]}`;

  // Voice-chat choices change which models a run needs.
  useEffect(() => {
    const t = setTimeout(() => void api.models_status(true).then((s) => setModels(s.models)), 500);
    return () => clearTimeout(t);
  }, [voiceKey]);
  const missing = models?.filter((m) => !m.ready) ?? [];

  const folder = async (key: "captures_folder" | "final_clips_folder" | "data_folder") => {
    const r = await api.choose_setting_folder(key);
    apply(r);
    if (key === "captures_folder" && r && !("error" in r)) void loadClips(true);
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel title="Folders" bodyClassName="p-0">
        <FolderRow title="Recordings" detail="Where your recorder saves CS2 videos." path={values.captures_folder} onChange={() => void folder("captures_folder")} />
        <FolderRow title="Clips" detail="Where finished highlights go." path={resolved.final_clips_folder} onChange={() => void folder("final_clips_folder")} />
        <FolderRow title="Working data" detail="Analysis results, thumbnails and the laughter model." path={resolved.data_folder} onChange={() => void folder("data_folder")} />
      </Panel>

      <Panel title="Your in-game name" aside={<span className="text-[13px] text-fg-faint">Optional</span>}>
        <PlayerNames value={values.player_names} onChange={(n) => setSetting("player_names", n, 0)} />
        <p className="mt-2.5 text-[13.5px] leading-relaxed text-fg-faint">
          CHAOS reads your name off the killfeed by itself. Add it only if your kills get missed, or you play under more than one name.
        </p>
      </Panel>

      <Panel title="Killfeed region" aside={<Button size="sm" onClick={() => setEditing(true)}>Edit region</Button>}>
        <div className="grid grid-cols-[1fr_200px] items-start gap-5">
          <RegionPreview roi={values.killfeed_roi} resolution={values.killfeed_roi_resolution} onEdit={() => setEditing(true)} />
          <div className="text-[13.5px] leading-relaxed text-fg-faint">
            The part of the screen CHAOS reads kills from. If kills get missed, check the box covers the whole killfeed.
            <div className="mt-3 font-mono text-[12px] text-fg-muted">
              {values.killfeed_roi.join(", ")}
              {values.killfeed_roi_resolution && <div>at {values.killfeed_roi_resolution.join("×")}</div>}
            </div>
          </div>
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
      </Panel>

      <Panel title="Voice chat" bodyClassName="p-0">
        <Row title="Clips without kills" detail="Save funny moments and conversations from voice chat even when nobody got a kill.">
          <Segmented
            value={values["moments.mode"]}
            options={[
              ["off", "Off"],
              ["funny", "Funny only"],
              ["conversations", "Funny + talks"],
            ]}
            onChange={(v) => setSetting("moments.mode", v as SettingsValues["moments.mode"], 0)}
          />
        </Row>
        <Row
          title="Subtitles"
          detail="Burn voice-chat captions into each clip and save an .srt next to it. Clipping takes longer, since clips get re-encoded."
        >
          <Toggle on={values["subtitles.enabled"]} label="Subtitles" onChange={(on) => setSetting("subtitles.enabled", on, 0)} />
        </Row>
      </Panel>

      <Panel
        title="AI models"
        aside={
          missing.length > 0 && (
            <Button size="sm" variant="primary" onClick={() => setGate(models)}>
              <Download className="size-4" /> Download {fmtSize(missing.reduce((n, m) => n + m.mb * (1 << 20), 0))}
            </Button>
          )
        }
        bodyClassName="p-0"
      >
        {!models ? (
          <div className="px-4 py-3.5 text-[14px] text-fg-faint">Checking…</div>
        ) : (
          models.map((m) => (
            <Row key={m.id} title={m.label} className="py-2.5">
              <span className="font-mono text-[12.5px] text-fg-faint">{fmtSize(m.mb * (1 << 20))}</span>
              <span className={cn("w-28 text-right text-[13.5px]", m.ready ? "text-secondary-hi" : "text-warn")}>{m.ready ? "Downloaded" : "Needed"}</span>
            </Row>
          ))
        )}
      </Panel>

      <AnimatePresence>
        {gate && (
          <motion.div className="fixed inset-0 z-50 bg-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <ModelGate
              models={gate}
              onReady={() => {
                setGate(null);
                void api.models_status(true).then((s) => setModels(s.models));
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function FolderRow({ title, detail, path, onChange }: { title: string; detail: string; path: string; onChange: () => void }) {
  return (
    <Row title={title} detail={detail}>
      <div className="flex min-w-0 max-w-[50%] items-center gap-2 text-[14px] text-fg-muted">
        <FolderOpen className="size-4 shrink-0 text-fg-faint" />
        <span className="truncate" title={path}>
          {path || <span className="text-warn">Not set</span>}
        </span>
      </div>
      <Button size="sm" onClick={onChange}>
        Change
      </Button>
    </Row>
  );
}

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex shrink-0 border border-line-strong bg-black/25">
      {options.map(([v, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className={cn(
            "display px-3 py-1.5 text-[13.5px] font-semibold tracking-[0.06em] transition-colors",
            v === value ? "bg-accent text-accent-ink" : "text-fg-muted hover:bg-white/[0.06] hover:text-fg",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ================================================================= detection

// OpenCV hue runs 0..180 for 0..360 degrees.
const HUE_TRACK = `linear-gradient(90deg, ${Array.from({ length: 13 }, (_, i) => `hsl(${i * 30} 90% 50%) ${(i / 12) * 100}%`).join(", ")})`;

function Detection({ values, defaults }: { values: SettingsValues; defaults: SettingsValues }) {
  const [confirm, setConfirm] = useState(false);
  const num = (key: keyof SettingsValues, title: string, detail: string, min: number, max: number, step: number, unit = "") => {
    const v = values[key] as number;
    const changed = v !== defaults[key];
    return (
      <Row key={key} title={title} detail={detail}>
        <div className="flex w-[300px] shrink-0 items-center gap-4">
          <Slider label={title} value={v} min={min} max={max} step={step} onChange={(x) => setSetting(key, x as never)} />
          <span className={cn("w-14 text-right font-mono text-[13px] tabular", changed ? "text-accent" : "text-fg-muted")} title={changed ? `Default ${defaults[key]}${unit}` : undefined}>
            {step < 1 ? v.toFixed(1) : v}
            {unit}
          </span>
        </div>
      </Row>
    );
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start gap-3 border border-warn/30 bg-warn/[0.06] px-4 py-3 text-[14px] leading-relaxed text-fg-muted">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
        <div className="flex-1">
          Fine-tuning for how kills are found and scored. Wrong values make CHAOS miss kills; changed values show in orange, and Reset puts
          the defaults back. Takes effect on the next run.
        </div>
        <Button size="sm" variant="ghost" onClick={() => setConfirm(true)}>
          <RotateCcw className="size-4" /> Reset
        </Button>
      </div>

      <Panel title="Killfeed border colour" bodyClassName="p-0">
        <div className="border-b border-line px-4 py-3 text-[13.5px] leading-relaxed text-fg-faint">
          Your own kills have a red border in the killfeed. Red sits at both ends of the hue wheel, so there are two ranges.
        </div>
        <HsvRange label="Range 1" lo={values.red_hsv_lower1} hi={values.red_hsv_upper1} loKey="red_hsv_lower1" hiKey="red_hsv_upper1" defaults={defaults} />
        <HsvRange label="Range 2" lo={values.red_hsv_lower2} hi={values.red_hsv_upper2} loKey="red_hsv_lower2" hiKey="red_hsv_upper2" defaults={defaults} />
      </Panel>

      <Panel title="Killfeed rows" bodyClassName="p-0">
        {num("killfeed_rect_min_height", "Shortest row", "Rows shorter than this aren't kills. Pixels at the region's resolution.", 10, 100, 1, "px")}
        {num("killfeed_rect_max_height", "Tallest row", "Rows taller than this aren't kills.", 20, 200, 1, "px")}
        {num("killfeed_rect_min_aspect_ratio", "Narrowest row", "How many times wider than tall a row must be.", 1, 20, 0.1, "×")}
      </Panel>

      <Panel title="Timing" bodyClassName="p-0">
        {num("killfeed_sample_interval_seconds", "Check the killfeed every", "Your kills stay up 7.5 s, so 2.5 s sees each one about three times. Lower is slower.", 0.5, 7, 0.5, "s")}
        {num("clip_pre_buffer_seconds", "Start clips before the action", "Seconds of lead-in before the first kill.", 0, 30, 0.5, "s")}
        {num("clip_post_buffer_seconds", "Keep going after", "Seconds after the last kill.", 0, 30, 0.5, "s")}
      </Panel>

      <Panel title="Scoring" bodyClassName="p-0">
        <div className="border-b border-line px-4 py-3 text-[13.5px] text-fg-faint">How much each thing adds to a clip's score. Highlights are ranked by score.</div>
        {num("scoring_weights.kill", "Each kill", "", 0, 100, 1)}
        {num("scoring_weights.multi_kill_bonus", "Multi-kill bonus", "Two or more kills close together.", 0, 100, 1)}
        {num("scoring_weights.headshot_bonus", "Headshot bonus", "", 0, 200, 1)}
        {num("scoring_weights.smoke_kill_bonus", "Through-smoke bonus", "", 0, 200, 1)}
        {num("scoring_weights.team_hype_voice", "Team hype", "Your team reacting on voice chat.", 0, 100, 1)}
        {num("scoring_weights.audio_spike", "Loud reaction", "A sudden spike in volume.", 0, 100, 1)}
        {num("scoring_weights.banter", "Funny moment", "Laughter and banter, for clips without kills.", 0, 100, 1)}
      </Panel>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Reset detection tuning?" width={460}>
        <p className="text-[15px] leading-relaxed text-fg-muted">
          Puts every setting on this tab back to its default. Folders, your name, the killfeed region and voice chat aren&apos;t touched.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirm(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={async () => {
              setConfirm(false);
              apply(await api.settings_reset_tuning());
            }}
          >
            Reset
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function HsvRange({
  label,
  lo,
  hi,
  loKey,
  hiKey,
  defaults,
}: {
  label: string;
  lo: Hsv;
  hi: Hsv;
  loKey: keyof SettingsValues;
  hiKey: keyof SettingsValues;
  defaults: SettingsValues;
}) {
  const changed = JSON.stringify([lo, hi]) !== JSON.stringify([defaults[loKey], defaults[hiKey]]);
  const set = (ch: 0 | 1 | 2, [a, b]: [number, number]) => {
    const nlo = [...lo] as Hsv;
    const nhi = [...hi] as Hsv;
    nlo[ch] = a;
    nhi[ch] = b;
    setSetting(loKey, nlo as never);
    setSetting(hiKey, nhi as never);
  };
  const mid = (lo[0] + hi[0]) / 2;
  const channels: [string, number, string][] = [
    ["Hue", 180, HUE_TRACK],
    ["Saturation", 255, `linear-gradient(90deg, hsl(${mid * 2} 0% 50%), hsl(${mid * 2} 100% 50%))`],
    ["Brightness", 255, `linear-gradient(90deg, #000, hsl(${mid * 2} 90% 50%))`],
  ];
  return (
    <div className="border-b border-line px-4 py-3.5 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className={cn("font-medium", changed && "text-accent")}>{label}</span>
        {/* the colours this range accepts */}
        <span
          className="h-3 w-24 border border-line-strong"
          style={{ background: `linear-gradient(90deg, hsl(${lo[0] * 2} ${(lo[1] / 255) * 100}% ${(lo[2] / 255) * 50}%), hsl(${hi[0] * 2} ${(hi[1] / 255) * 100}% ${(hi[2] / 255) * 50}%))` }}
        />
      </div>
      <div className="mt-2 grid grid-cols-[96px_1fr_88px] items-center gap-x-4 gap-y-1">
        {channels.map(([name, max, track], ch) => (
          <Channel key={name} name={name} max={max} track={track} value={[lo[ch], hi[ch]]} onChange={(v) => set(ch as 0 | 1 | 2, v)} />
        ))}
      </div>
    </div>
  );
}

function Channel({ name, max, track, value, onChange }: { name: string; max: number; track: string; value: [number, number]; onChange: (v: [number, number]) => void }) {
  return (
    <>
      <Label>{name}</Label>
      <RangeSlider label={name} value={value} min={0} max={max} onChange={onChange} track={track} />
      <span className="text-right font-mono text-[12.5px] text-fg-muted tabular">
        {value[0]} to {value[1]}
      </span>
    </>
  );
}

// ================================================================= appearance

function Appearance() {
  const background = prefs.use((s) => s.background);
  const motionOn = prefs.use((s) => s.background_motion);
  return (
    <Panel title="Appearance" bodyClassName="p-0">
      <Row title={<span className="flex items-center gap-2.5"><Monitor className="size-4 text-fg-faint" /> Background</span>} detail="The dim room behind the app. Off gives a plain dark background.">
        <Toggle on={background} label="Background" onChange={(on) => void setPref({ background: on })} />
      </Row>
      <Row
        title={<span className="flex items-center gap-2.5"><MoveHorizontal className="size-4 text-fg-faint" /> Background motion</span>}
        detail={background ? "Lets the room turn slightly as you move the mouse. Off keeps it completely still." : "Turn the background on to use this."}
        className={cn(!background && "opacity-50")}
      >
        <div className={cn(!background && "pointer-events-none")}>
          <Toggle on={background && motionOn} label="Background motion" onChange={(on) => void setPref({ background_motion: on })} />
        </div>
      </Row>
    </Panel>
  );
}

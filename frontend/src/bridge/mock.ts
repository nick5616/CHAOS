import { dispatchChaos } from "./events";
import type { ChaosApi, ClipEvent, GpuInfo, Highlight, Job, ModelInfo, RunSnapshot, SettingsBundle, SettingsValues, Thumb, UiPrefs, Video } from "./types";

// A fake host for developing in a normal browser. URL params pick a scenario:
//   ?models=ready|missing|error   (default ready)
//   ?gpu=cuda|nocuda|cpu          (default cuda)
//   ?folder=ok|none|empty         (default ok)
//   ?space=ok|low                 (default ok)

const params = new URLSearchParams(location.search);
const scenario = params.get("models") ?? "ready";
const MB = 1 << 20;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const MODELS: ModelInfo[] = [
  { id: "craft_mlt_25k.pth", label: "Killfeed text detector", mb: 79, ready: true },
  { id: "english_g2.pth", label: "Killfeed text reader", mb: 14, ready: true },
  { id: "base.pt", label: "Whisper speech model (base)", mb: 142, ready: true },
  { id: "Cnn14_16k_mAP=0.438.pth", label: "Laughter detector", mb: 360, ready: true },
];
if (scenario !== "ready") MODELS.forEach((m) => (m.ready = false));

const GPUS: Record<string, GpuInfo> = {
  cuda: { cuda_available: true, gpu_present: true, gpu_name: "NVIDIA GeForce RTX 3070", driver_version: "566.36", max_cuda_version: "12.7" },
  nocuda: { cuda_available: false, gpu_present: true, gpu_name: "NVIDIA GeForce RTX 3070", driver_version: "566.36", max_cuda_version: "12.7" },
  cpu: { cuda_available: false, gpu_present: false, gpu_name: null, driver_version: null, max_cuda_version: null },
};

// ---------------------------------------------------------------- models

let failedOnce = false;
let downloading = false;

async function download() {
  const todo = MODELS.filter((m) => !m.ready);
  const sizes = Object.fromEntries(todo.map((m) => [m.id, m.mb * MB]));
  const overallTotal = todo.reduce((s, m) => s + m.mb * MB, 0);
  let finished = 0;
  for (const m of todo) {
    let done = 0;
    while (done < sizes[m.id]) {
      await sleep(100);
      const speed = (34 + Math.random() * 10) * MB;
      done = Math.min(sizes[m.id], done + speed / 10);
      if (scenario === "error" && !failedOnce && m.id === "base.pt" && done > sizes[m.id] / 2) {
        failedOnce = true;
        dispatchChaos("models:error", {
          id: m.id,
          kind: "offline",
          message: "Couldn't reach the download server. Check your internet connection and try again.",
        });
        return;
      }
      const overall = finished + done;
      dispatchChaos("models:progress", {
        id: m.id, state: "downloading", done, total: sizes[m.id],
        overall_done: overall, overall_total: overallTotal,
        bytes_per_sec: speed, eta_sec: (overallTotal - overall) / speed,
      });
    }
    const base = { id: m.id, done, total: sizes[m.id], overall_done: finished + done, overall_total: overallTotal, bytes_per_sec: 0, eta_sec: null };
    dispatchChaos("models:progress", { ...base, state: "verifying" });
    await sleep(500);
    m.ready = true;
    finished += sizes[m.id];
    dispatchChaos("models:progress", { ...base, state: "done" });
  }
  dispatchChaos("models:done", {});
}

// ---------------------------------------------------------------- clips

const FOLDER = "D:\\Captures\\Counter-strike 2";

function makeVideos(): Video[] {
  if (params.get("folder") === "empty") return [];
  const out: Video[] = [];
  const day0 = new Date(2026, 9, 29, 1, 51, 26);
  let rnd = 7;
  const r = () => ((rnd = (rnd * 16807) % 2147483647) / 2147483647);
  for (let d = 0; d < 7; d++) {
    const n = 3 + Math.floor(r() * 9);
    for (let i = 0; i < n; i++) {
      const t = new Date(day0.getTime() - d * 86400e3 * (1 + Math.floor(r() * 3)) - i * (600e3 + r() * 1800e3));
      const p = (x: number) => String(x).padStart(2, "0");
      const name = `Counter-strike 2 ${t.getFullYear()}.${p(t.getMonth() + 1)}.${p(t.getDate())} - ${p(t.getHours())}.${p(t.getMinutes())}.${p(t.getSeconds())}.${p(Math.floor(r() * 99))}.DVR.mp4`;
      out.push({ path: `${FOLDER}\\${name}`, name, size: Math.floor((150 + r() * 600) * 1e6), recorded: t.toISOString().slice(0, 19), url: "" });
    }
  }
  return out.sort((a, b) => b.recorded.localeCompare(a.recorded));
}

const VIDEOS = makeVideos();

/** A stand-in frame: dusty sky, a wall, a crosshair and a killfeed. */
function fakeThumb(seed: number): string {
  const hue = [28, 32, 200, 210, 40][seed % 5];
  const rows = 1 + (seed % 3);
  const feed = Array.from({ length: rows }, (_, i) =>
    `<rect x="300" y="${14 + i * 15}" width="${150 - (i % 2) * 22}" height="11" rx="1" fill="rgba(0,0,0,.55)" stroke="${i === 0 && seed % 2 ? "#e53" : "none"}"/>`,
  ).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270" viewBox="0 0 480 270">
<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="hsl(${hue},35%,62%)"/><stop offset="1" stop-color="hsl(${hue},30%,38%)"/></linearGradient></defs>
<rect width="480" height="270" fill="url(#s)"/>
<rect y="${150 + (seed % 4) * 10}" width="480" height="140" fill="hsl(${hue},22%,${24 + (seed % 3) * 4}%)"/>
<rect x="${40 + (seed * 37) % 200}" y="70" width="${90 + (seed % 5) * 20}" height="130" fill="hsl(${hue},18%,${30 + (seed % 4) * 5}%)"/>
<g stroke="#5f5" stroke-width="2"><line x1="240" y1="127" x2="240" y2="133"/><line x1="240" y1="137" x2="240" y2="143"/><line x1="230" y1="135" x2="236" y2="135"/><line x1="244" y1="135" x2="250" y2="135"/></g>
${feed}
<rect x="16" y="242" width="54" height="14" fill="rgba(0,0,0,.4)"/><rect x="410" y="242" width="54" height="14" fill="rgba(0,0,0,.4)"/>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const thumbCache: Record<string, Thumb> = {};

// ---------------------------------------------------------------- highlights

const LINES = ["Where did he go?", "He's at his house, he's at his house!", "No way.", "Bro what was that", "One B, one B", "Nice!", "I'm pissed about that."];
const NAMES = ["ngs", "BOT Mayer", "BOT Opie", "s1mple fan", "xX_noob_Xx", "dad"];

function makeHighlights(): Highlight[] {
  if (params.get("highlights") === "none") return [];
  const out: Highlight[] = [];
  const specs: [Highlight["kind"], number, string[], number][] = [
    ["kill", 3615, ["headshot", "loud_reaction", "multi-kill"], 5],
    ["kill", 560, ["headshot", "multi-kill"], 3],
    ["funny", 137, ["funny", "laughter", "running_bit"], 0],
    ["kill", 195, ["headshot", "multi-kill"], 2],
    ["kill", 130, ["headshot", "wallbang"], 1],
    ["conversation", 13, ["conversation", "running_bit"], 0],
    ["kill", 65, ["headshot"], 1],
    ["kill", 60, ["through_smoke"], 1],
    ["kill", 10, [], 1],
  ];
  specs.forEach(([kind, score, tags, kills], i) => {
    const v = VIDEOS[i % VIDEOS.length];
    const length = kind === "kill" ? 16 + kills * 9 : 48;
    const events: ClipEvent[] = [];
    for (let k = 0; k < kills; k++)
      events.push({
        type: "kill",
        t: 6 + k * 6.5,
        details: { victim: NAMES[(i + k) % NAMES.length], inferred_player: "hot dog dog", isHeadshot: k % 2 === 0, wallbang: tags.includes("wallbang") && k === 0, throughSmoke: tags.includes("through_smoke") },
      });
    for (let k = 0; k < (kind === "kill" ? 2 : 7); k++)
      events.push({ type: "voice", t: 3 + k * 6.1, details: { text: LINES[(i + k) % LINES.length], end: 3 + k * 6.1 + 1.6 } });
    if (kind !== "kill") events.push({ type: "laughter", t: 21, details: { confidence: 0.8 } });
    if (tags.includes("loud_reaction")) events.push({ type: "audio_spike", t: 13.2, details: { intensity: 0.95 } });
    events.sort((a, b) => a.t - b.t);
    out.push({
      rank: i + 1, kind, score, tags, source: v.name, length, file: v.path, file_name: `${i + 1}_${score}.mp4`,
      size: Math.floor(length * 1.4e6), url: "", kills, events,
    });
  });
  return out;
}

// ---------------------------------------------------------------- run

let snapshot: RunSnapshot = {
  running: false, started_at: null, finished: null, total: 0, done: 0, workers: null,
  gaming: false, jobs: {}, order: [], log: [],
};
let stopRequested = false;

const prefs: UiPrefs = {
  background: params.get("bg") !== "off",
  background_motion: params.get("motion") !== "off",
};

function log(text: string, level: "info" | "error" = "info") {
  const entry = { t: Date.now() / 1000, level, text };
  snapshot.log.push(entry);
  dispatchChaos("run:log", entry);
}

function job(name: string, changes: Partial<Job>) {
  const j: Job = { ...(snapshot.jobs[name] ?? { name, stage: "queued", clips: null }), ...changes };
  snapshot.jobs[name] = j;
  if (!snapshot.order.includes(name)) snapshot.order.push(name);
  dispatchChaos("run:job", j);
}

async function simulateRun(paths: string[], workers: number | null) {
  const names = paths.map((p) => p.split("\\").pop()!);
  snapshot = {
    running: true, started_at: Date.now() / 1000, finished: null, total: names.length, done: 0,
    workers: workers ?? 3, gaming: snapshot.gaming, jobs: {}, order: [], log: [],
  };
  stopRequested = false;
  dispatchChaos("run:started", structuredClone(snapshot));
  log("Starting CHAOS pipeline…");
  await sleep(600);
  log("CUDA: 3 analysis workers (max 4, limited by vram). RTX 3070, 7.1 GB free");
  dispatchChaos("run:workers", { n: snapshot.workers! });
  names.forEach((n) => job(n, { stage: "queued" }));
  let next = 0;
  let clipsTotal = 0;
  const worker = async () => {
    while (next < names.length && !stopRequested) {
      const n = names[next++];
      job(n, { stage: "analyze" });
      await sleep(2200 + Math.random() * 2600);
      if (stopRequested) return;
      if (n.includes(".07.")) {
        log(`Analyze failed ${n}: moov atom not found`, "error");
        job(n, { stage: "failed" });
      } else {
        const c = Math.floor(Math.random() * 4);
        job(n, { stage: "correlate", clips: c });
        log(`${n}: ${c} clip(s) found`);
        await sleep(500);
        job(n, { stage: "clip" });
        await sleep(700);
        clipsTotal += c;
        job(n, { stage: "done" });
      }
      snapshot.done++;
      dispatchChaos("run:count", { done: snapshot.done, total: snapshot.total });
    }
  };
  await Promise.all(Array.from({ length: snapshot.gaming ? 1 : snapshot.workers! }, worker));
  const ok = !stopRequested;
  if (ok) log("Summary generated");
  else log("Pipeline stopped", "error");
  snapshot.running = false;
  snapshot.finished = { success: ok, elapsed: Date.now() / 1000 - snapshot.started_at!, clips: clipsTotal };
  dispatchChaos("run:finished", snapshot.finished);
}

// ---------------------------------------------------------------- settings

const DEFAULTS: SettingsValues = {
  captures_folder: FOLDER, data_folder: "./data", final_clips_folder: "D:\\CHAOS Clips", player_names: [],
  killfeed_roi: [1978, 40, 2540, 333], killfeed_roi_resolution: [2560, 1440],
  "moments.mode": "conversations", "subtitles.enabled": false, "gui.setup_complete": true,
  killfeed_rect_min_height: 25, killfeed_rect_max_height: 50, killfeed_rect_min_aspect_ratio: 5,
  killfeed_sample_interval_seconds: 2.5, clip_pre_buffer_seconds: 7, clip_post_buffer_seconds: 6,
  "scoring_weights.kill": 10, "scoring_weights.multi_kill_bonus": 15, "scoring_weights.headshot_bonus": 50,
  "scoring_weights.smoke_kill_bonus": 40, "scoring_weights.team_hype_voice": 20, "scoring_weights.audio_spike": 5,
  "scoring_weights.banter": 20,
  red_hsv_lower1: [0, 120, 70], red_hsv_upper1: [10, 255, 255], red_hsv_lower2: [170, 120, 70], red_hsv_upper2: [180, 255, 255],
};
const values: SettingsValues = { ...DEFAULTS, "gui.setup_complete": params.get("setup") !== "new" };
if (params.get("setup") === "new") values.captures_folder = "";

const bundle = (): SettingsBundle => ({
  values: structuredClone(values),
  defaults: structuredClone(DEFAULTS),
  resolved: { data_folder: "C:\\CHAOS\\data", final_clips_folder: values.final_clips_folder },
});

// ---------------------------------------------------------------- the API

export function createMock(): ChaosApi {
  const gpu = GPUS[params.get("gpu") ?? "cuda"] ?? GPUS.cuda;
  setTimeout(() => dispatchChaos("system:gpu", gpu), 1500);
  const noFolder = params.get("folder") === "none";
  return {
    app_info: async () => ({ version: "1.0.0", dev: true, platform: "mock" }),
    models_status: async () => {
      await sleep(700);
      return { models: MODELS.map((m) => ({ ...m })), error: null };
    },
    download_models: async () => {
      if (downloading) return { started: false };
      downloading = true;
      void download().finally(() => (downloading = false));
      return { started: true };
    },
    gpu_info: async () => ({ ...gpu, checking: true }),

    list_clips: async () => {
      await sleep(200);
      return noFolder || !values.captures_folder ? { folder: "", exists: false, videos: [] } : { folder: FOLDER, exists: true, videos: VIDEOS };
    },
    choose_captures_folder: async () => ({ folder: FOLDER, exists: true, videos: VIDEOS }),
    request_thumbnails: async (paths) => {
      const ready: Thumb[] = [];
      for (const p of paths) {
        if (thumbCache[p]) ready.push(thumbCache[p]);
        else
          setTimeout(() => {
            const i = VIDEOS.findIndex((v) => v.path === p);
            thumbCache[p] = { path: p, url: fakeThumb(i), duration: 60 + ((i * 53) % 120) };
            dispatchChaos("clips:thumb", thumbCache[p]);
          }, 150 + Math.random() * 600);
      }
      return ready;
    },
    open_captures_folder: async () => {},

    highlights: async () => ({ clips: makeHighlights(), clips_folder: "D:\\CHAOS Clips", found: params.get("highlights") !== "none" }),
    reveal_file: async () => true,
    export_sequence: async () => {
      void (async () => {
        for (let f = 0; f <= 1.0001; f += 0.05) {
          await sleep(120);
          dispatchChaos("export:progress", { fraction: Math.min(1, f) });
        }
        dispatchChaos("export:done", { ok: true, path: "D:\\CHAOS Clips\\chaos_highlights.mp4", mode: "copy", message: "" });
      })();
      return true;
    },

    run_setup: async () => ({
      player_names: [],
      clips_folder: "D:\\CHAOS Clips",
      free_bytes: params.get("space") === "low" ? 2.1e9 : 412e9,
      low_space: params.get("space") === "low",
      workers: null,
    }),
    worker_plan: async () => {
      await sleep(300);
      return { device: "cuda", workers: 3, max_workers: 4, summary: "CUDA: 3 analysis workers (max 4, limited by vram)." };
    },
    save_player_names: async (names) => names,
    choose_clips_folder: async () => ({ player_names: [], clips_folder: "E:\\Clips", free_bytes: 900e9, low_space: false, workers: null }),
    open_clips_folder: async () => {},

    start_run: async (paths, workers) => {
      if (snapshot.running) return { ok: false, error: "running" };
      if (MODELS.some((m) => !m.ready)) return { ok: false, error: "models_missing" };
      void simulateRun(paths, workers);
      return { ok: true };
    },
    stop_run: async () => {
      stopRequested = true;
      log("Stopping pipeline…");
    },
    set_run_workers: async (n) => {
      snapshot.workers = n;
      dispatchChaos("run:workers", { n });
    },
    set_gaming: async (on) => {
      snapshot.gaming = on;
      dispatchChaos("run:gaming", { on });
    },
    run_snapshot: async () => structuredClone(snapshot),
    export_log: async () => true,

    settings_get: async () => bundle(),
    settings_set: async (patch) => {
      Object.assign(values, patch);
      return bundle();
    },
    settings_reset_tuning: async () => {
      for (const k of Object.keys(DEFAULTS) as (keyof SettingsValues)[])
        if (/^(killfeed_rect|killfeed_sample|clip_|scoring_weights|red_hsv)/.test(k)) (values as unknown as Record<string, unknown>)[k] = structuredClone(DEFAULTS[k]);
      return bundle();
    },
    choose_setting_folder: async (key) => {
      (values as unknown as Record<string, unknown>)[key] = key === "captures_folder" ? FOLDER : "E:\\Picked";
      return bundle();
    },
    system_check: async () => ({
      python: { ok: true, detail: "3.12.6" },
      ffmpeg: { ok: true, detail: "ffmpeg version 8.0" },
      setup_complete: values["gui.setup_complete"],
    }),
    detect_resolution: async () => [2560, 1440],
    roi_frame: async (index = 0, fraction = 0.35) => ({
      url: fakeThumb(index), width: 2560, height: 1440, name: VIDEOS[index]?.name ?? "x.mp4",
      recorded: VIDEOS[index]?.recorded ?? "", t: fraction * 120, duration: 120, index, count: Math.min(VIDEOS.length, 25),
    }),
    ui_prefs: async () => ({ ...prefs }),
    set_ui_prefs: async (p) => Object.assign(prefs, p),

    cuda_install_command: async () => "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126",
    install_cuda: async () => {
      void (async () => {
        for (const line of ["Looking in indexes: https://download.pytorch.org/whl/cu126", "Collecting torch", "Downloading torch-2.8.0+cu126 (2.4 GB)", "Installing collected packages: torch", "Successfully installed torch-2.8.0+cu126"]) {
          await sleep(700);
          dispatchChaos("cuda:output", { line });
        }
        dispatchChaos("cuda:done", { success: true });
      })();
      return true;
    },
    restart_app: async () => location.reload(),
  };
}

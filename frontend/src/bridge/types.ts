// Every call and event between the page and the Python host
// (desktop_app/web/api.py). Keys stay snake_case, as Python sends them.

export interface AppInfo {
  version: string;
  dev: boolean;
  platform: string;
}

// ---------------------------------------------------------------- models

export interface ModelInfo {
  id: string;
  label: string;
  mb: number;
  ready: boolean;
}

export interface ModelsStatus {
  models: ModelInfo[];
  /** Set when the check itself failed (e.g. a broken install). */
  error: string | null;
}

export type ModelState = "waiting" | "downloading" | "verifying" | "done" | "error";

export interface ModelsProgress {
  id: string;
  state: Exclude<ModelState, "waiting" | "error">;
  done: number;
  total: number;
  overall_done: number;
  overall_total: number;
  bytes_per_sec: number;
  eta_sec: number | null;
}

export interface ModelsError {
  id: string | null;
  kind: "offline" | "server" | "checksum" | "disk" | "other";
  message: string;
}

// ---------------------------------------------------------------- system

export interface GpuInfo {
  cuda_available: boolean;
  gpu_present: boolean;
  gpu_name: string | null;
  driver_version: string | null;
  max_cuda_version: string | null;
  /** True while the startup check is running and this is last run's result. */
  checking?: boolean;
}

// ---------------------------------------------------------------- clips

export interface Video {
  path: string;
  name: string;
  size: number;
  /** ISO local time: from ShadowPlay's file name, else the file's mtime. */
  recorded: string;
  /** Playable URL from the media server. */
  url: string;
}

export interface ClipList {
  folder: string;
  exists: boolean;
  videos: Video[];
}

export interface Thumb {
  path: string;
  /** null when ffmpeg couldn't read the file. */
  url: string | null;
  duration: number | null;
}

// ---------------------------------------------------------------- run

export interface RunSetup {
  player_names: string[];
  clips_folder: string;
  free_bytes: number | null;
  low_space: boolean;
  /** Saved worker count, null for auto. */
  workers: number | null;
}

export interface WorkerPlan {
  device: string;
  workers: number;
  max_workers: number;
  summary: string;
}

export type JobStage = "queued" | "analyze" | "correlate" | "clip" | "done" | "failed";

export interface Job {
  name: string;
  stage: JobStage;
  clips: number | null;
}

export interface LogEntry {
  t: number;
  level: "info" | "error";
  text: string;
}

export interface RunFinished {
  success: boolean;
  elapsed: number;
  clips: number;
}

export interface RunSnapshot {
  running: boolean;
  /** Epoch seconds. */
  started_at: number | null;
  finished: RunFinished | null;
  total: number;
  done: number;
  workers: number | null;
  gaming: boolean;
  jobs: Record<string, Job>;
  order: string[];
  log: LogEntry[];
}

export type StartError = "no_videos" | "models_missing" | "running";

// ---------------------------------------------------------------- highlights

export type EventType = "kill" | "voice" | "chat" | "laughter" | "audio_spike";

export interface KillDetails {
  victim?: string;
  inferred_player?: string;
  detected_player?: string;
  assister?: string;
  attackerBlind?: boolean;
  inAir?: boolean;
  noScope?: boolean;
  throughSmoke?: boolean;
  wallbang?: boolean;
  isHeadshot?: boolean;
}

export interface ClipEvent {
  type: EventType;
  /** Seconds from the start of the clip file. */
  t: number;
  details: KillDetails & { text?: string; end?: number; confidence?: number; intensity?: number };
}

export interface Highlight {
  rank: number;
  kind: "kill" | "funny" | "conversation";
  score: number;
  tags: string[];
  /** The recording it was cut from (file name). */
  source: string;
  length: number;
  /** Null when the clip file is gone from the clips folder. */
  file: string | null;
  file_name: string | null;
  size: number;
  url: string | null;
  kills: number;
  events: ClipEvent[];
}

export interface HighlightList {
  clips: Highlight[];
  clips_folder: string;
  /** False when there's no ordered_highlights.json yet. */
  found: boolean;
}

// ---------------------------------------------------------------- settings

export type Hsv = [number, number, number];
export type Roi = [number, number, number, number];

/** config.yaml values by dotted key (see desktop_app/web/settings.py). */
export interface SettingsValues {
  captures_folder: string;
  data_folder: string;
  final_clips_folder: string;
  player_names: string[];
  killfeed_roi: Roi;
  killfeed_roi_resolution: [number, number] | null;
  "moments.mode": "off" | "funny" | "conversations";
  "subtitles.enabled": boolean;
  "gui.setup_complete": boolean;
  killfeed_rect_min_height: number;
  killfeed_rect_max_height: number;
  killfeed_rect_min_aspect_ratio: number;
  killfeed_sample_interval_seconds: number;
  clip_pre_buffer_seconds: number;
  clip_post_buffer_seconds: number;
  "scoring_weights.kill": number;
  "scoring_weights.multi_kill_bonus": number;
  "scoring_weights.headshot_bonus": number;
  "scoring_weights.smoke_kill_bonus": number;
  "scoring_weights.team_hype_voice": number;
  "scoring_weights.audio_spike": number;
  "scoring_weights.banter": number;
  red_hsv_lower1: Hsv;
  red_hsv_upper1: Hsv;
  red_hsv_lower2: Hsv;
  red_hsv_upper2: Hsv;
}

export interface SettingsBundle {
  values: SettingsValues;
  defaults: SettingsValues;
  /** Folder settings resolved to absolute paths. */
  resolved: { data_folder: string; final_clips_folder: string };
}

export interface RoiFrame {
  url: string;
  width: number;
  height: number;
  name: string;
  recorded: string;
  t: number;
  duration: number;
  index: number;
  count: number;
}

export interface SystemCheck {
  python: { ok: boolean; detail: string };
  ffmpeg: { ok: boolean; detail: string };
  setup_complete: boolean;
}

// ---------------------------------------------------------------- appearance

export interface UiPrefs {
  /** Show the room behind the app at all. */
  background: boolean;
  /** Let it turn with the mouse and sway. */
  background_motion: boolean;
}

// ---------------------------------------------------------------- the bridge

export interface ChaosApi {
  app_info(): Promise<AppInfo>;
  models_status(refresh?: boolean): Promise<ModelsStatus>;
  download_models(): Promise<{ started: boolean }>;
  gpu_info(): Promise<GpuInfo>;

  list_clips(): Promise<ClipList>;
  choose_captures_folder(): Promise<ClipList | null>;
  request_thumbnails(paths: string[]): Promise<Thumb[]>;
  open_captures_folder(): Promise<void>;

  highlights(): Promise<HighlightList>;
  reveal_file(path: string): Promise<boolean>;
  /** Asks where to save; false if cancelled or nothing to export. */
  export_sequence(paths: string[]): Promise<boolean>;

  run_setup(): Promise<RunSetup>;
  worker_plan(): Promise<WorkerPlan>;
  save_player_names(names: string[]): Promise<string[]>;
  choose_clips_folder(): Promise<RunSetup>;
  open_clips_folder(): Promise<void>;

  start_run(paths: string[], workers: number | null): Promise<{ ok: boolean; error?: StartError }>;
  stop_run(): Promise<void>;
  set_run_workers(n: number): Promise<void>;
  set_gaming(on: boolean): Promise<void>;
  run_snapshot(): Promise<RunSnapshot>;
  export_log(text: string): Promise<boolean>;

  settings_get(): Promise<SettingsBundle>;
  settings_set(patch: Partial<SettingsValues>): Promise<SettingsBundle | { error: string }>;
  settings_reset_tuning(): Promise<SettingsBundle | { error: string }>;
  choose_setting_folder(key: "captures_folder" | "data_folder" | "final_clips_folder"): Promise<SettingsBundle | { error: string } | null>;
  system_check(): Promise<SystemCheck>;
  detect_resolution(): Promise<[number, number] | null>;
  roi_frame(index?: number, fraction?: number): Promise<RoiFrame | null>;

  ui_prefs(): Promise<UiPrefs>;
  set_ui_prefs(prefs: Partial<UiPrefs>): Promise<UiPrefs>;

  cuda_install_command(): Promise<string>;
  install_cuda(): Promise<boolean>;
  restart_app(): Promise<void>;
}

export interface ChaosEvents {
  "models:progress": ModelsProgress;
  "models:done": Record<string, never>;
  "models:error": ModelsError;
  "system:gpu": GpuInfo;
  "clips:thumb": Thumb;
  "run:started": RunSnapshot;
  "run:job": Job;
  "run:count": { done: number; total: number };
  "run:log": LogEntry;
  "run:workers": { n: number };
  "run:gaming": { on: boolean };
  "run:finished": RunFinished;
  "export:progress": { fraction: number };
  "export:done": { ok: boolean; path: string; mode: "copy" | "encode" | null; message: string };
  "cuda:output": { line: string };
  "cuda:done": { success: boolean };
}

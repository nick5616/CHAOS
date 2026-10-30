import { api, onChaos, type Thumb, type Video } from "../bridge";
import { createStore } from "../lib/store";

interface ClipsState {
  status: "idle" | "loading" | "ready";
  folder: string;
  exists: boolean;
  videos: Video[];
  thumbs: Record<string, Thumb>;
  /** Paths left out of the next run. Everything else is included. */
  excluded: Record<string, true>;
}

export const clips = createStore<ClipsState>({
  status: "idle",
  folder: "",
  exists: false,
  videos: [],
  thumbs: {},
  excluded: {},
});

export async function loadClips(force = false) {
  if (!force && clips.get().status !== "idle") return;
  clips.set({ status: "loading" });
  const list = await api.list_clips();
  clips.set({ status: "ready", folder: list.folder, exists: list.exists, videos: list.videos, excluded: {} });
}

export async function chooseCapturesFolder() {
  const list = await api.choose_captures_folder();
  if (list) clips.set({ status: "ready", folder: list.folder, exists: list.exists, videos: list.videos, thumbs: {}, excluded: {} });
}

export function setIncluded(paths: string[], include: boolean) {
  clips.set((s) => {
    const excluded = { ...s.excluded };
    for (const p of paths) {
      if (include) delete excluded[p];
      else excluded[p] = true;
    }
    return { excluded };
  });
}

export function includedPaths(): string[] {
  const { videos, excluded } = clips.get();
  return videos.filter((v) => !excluded[v.path]).map((v) => v.path);
}

// Thumbnails: cards ask as they scroll into view; asks are batched per frame.
let pending = new Set<string>();
let flushTimer: number | undefined;

export function wantThumb(path: string) {
  if (clips.get().thumbs[path]) return;
  pending.add(path);
  flushTimer ??= window.setTimeout(async () => {
    const batch = [...pending];
    pending = new Set();
    flushTimer = undefined;
    const ready = await api.request_thumbnails(batch);
    if (ready.length) addThumbs(ready);
  }, 40);
}

function addThumbs(list: Thumb[]) {
  clips.set((s) => {
    const thumbs = { ...s.thumbs };
    for (const t of list) thumbs[t.path] = t;
    return { thumbs };
  });
}

// Thumbnails arrive one by one; fold them into one update per frame.
let incoming: Thumb[] = [];
onChaos("clips:thumb", (t) => {
  if (!incoming.length) requestAnimationFrame(() => {
    addThumbs(incoming);
    incoming = [];
  });
  incoming.push(t);
});

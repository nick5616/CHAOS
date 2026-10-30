import { api, onChaos, type GpuInfo, type RunSnapshot } from "../bridge";
import { createStore } from "../lib/store";

// The run lives in Python; this mirrors it from `run:*` events so any screen
// (and the top bar) can show it, and it survives switching tabs.

const EMPTY: RunSnapshot = {
  running: false,
  started_at: null,
  finished: null,
  total: 0,
  done: 0,
  workers: null,
  gaming: false,
  jobs: {},
  order: [],
  log: [],
};

export const run = createStore<RunSnapshot>(EMPTY);

export async function syncRun() {
  run.set(await api.run_snapshot());
}

onChaos("run:started", (snap) => run.set(snap));
onChaos("run:job", (job) =>
  run.set((s) => ({
    jobs: { ...s.jobs, [job.name]: job },
    order: s.order.includes(job.name) ? s.order : [...s.order, job.name],
  })),
);
onChaos("run:count", ({ done, total }) => run.set({ done, total }));
onChaos("run:workers", ({ n }) => run.set({ workers: n }));
onChaos("run:gaming", ({ on }) => run.set({ gaming: on }));
onChaos("run:finished", (finished) => run.set({ running: false, finished }));

// Log lines can come in bursts; batch them into one update per frame.
let lines: RunSnapshot["log"] = [];
onChaos("run:log", (entry) => {
  if (!lines.length)
    requestAnimationFrame(() => {
      const batch = lines;
      lines = [];
      run.set((s) => ({ log: [...s.log, ...batch].slice(-3000) }));
    });
  lines.push(entry);
});

// ---------------------------------------------------------------- GPU

export const gpu = createStore<{ info: GpuInfo | null }>({ info: null });

export async function loadGpu() {
  const info = await api.gpu_info();
  gpu.set((s) => ({ info: s.info && !s.info.checking ? s.info : info }));
}

onChaos("system:gpu", (info) => gpu.set({ info: { ...info, checking: false } }));

/** "RTX 3070" from "NVIDIA GeForce RTX 3070". */
export function shortGpu(name: string | null | undefined): string {
  return (name ?? "GPU").replace(/^NVIDIA\s+/i, "").replace(/^GeForce\s+/i, "");
}

import { api, type SettingsBundle, type SettingsValues } from "../bridge";
import { createStore } from "../lib/store";

// Settings save themselves: a change shows at once, and is written to
// config.yaml a moment later (sliders send many changes; they're merged).

interface SettingsState {
  bundle: SettingsBundle | null;
  saving: boolean;
  savedAt: number | null;
  error: string | null;
}

export const settings = createStore<SettingsState>({ bundle: null, saving: false, savedAt: null, error: null });

export async function loadSettings() {
  settings.set({ bundle: await api.settings_get() });
}

let pending: Partial<SettingsValues> = {};
let timer: number | undefined;

export function setSetting<K extends keyof SettingsValues>(key: K, value: SettingsValues[K], delay = 350) {
  settings.set((s) => (s.bundle ? { bundle: { ...s.bundle, values: { ...s.bundle.values, [key]: value } }, error: null } : {}));
  pending = { ...pending, [key]: value };
  clearTimeout(timer);
  timer = window.setTimeout(flush, delay);
}

export function setSettings(patch: Partial<SettingsValues>) {
  for (const [k, v] of Object.entries(patch)) setSetting(k as keyof SettingsValues, v as never, 0);
}

async function flush() {
  const patch = pending;
  pending = {};
  if (!Object.keys(patch).length) return;
  settings.set({ saving: true });
  apply(await api.settings_set(patch));
}

export function apply(result: SettingsBundle | { error: string } | null) {
  if (!result) return settings.set({ saving: false });
  if ("error" in result) {
    settings.set({ saving: false, error: result.error });
    void loadSettings();     // show what's really saved
  } else settings.set({ bundle: result, saving: false, savedAt: Date.now(), error: null });
}

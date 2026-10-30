import { api, type UiPrefs } from "../bridge";
import { createStore } from "../lib/store";

export const prefs = createStore<UiPrefs & { loaded: boolean }>({
  background: true,
  background_motion: true,
  loaded: false,
});

export async function loadPrefs() {
  prefs.set({ ...(await api.ui_prefs()), loaded: true });
}

export async function setPref(change: Partial<UiPrefs>) {
  prefs.set(change);
  prefs.set(await api.set_ui_prefs(change));
}

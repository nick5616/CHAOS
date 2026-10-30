import { api, onChaos, type HighlightList } from "../bridge";
import { createStore } from "../lib/store";

export const highlights = createStore<{ status: "idle" | "loading" | "ready"; list: HighlightList | null }>({
  status: "idle",
  list: null,
});

export async function loadHighlights(force = false) {
  if (!force && highlights.get().status !== "idle") return;
  highlights.set({ status: "loading" });
  highlights.set({ status: "ready", list: await api.highlights() });
}

// A finished run rewrites the list.
onChaos("run:finished", () => void loadHighlights(true));

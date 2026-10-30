import type { HighlightList } from "../bridge";
import { createStore } from "../lib/store";
import { highlights } from "./highlights";

// The Watch sequence: which highlights play, in what order. Kept here so it
// survives switching tabs; a new highlights list (after a run) resets it.

interface WatchState {
  source: HighlightList | null;
  order: number[];        // ranks, in play order
  removed: number[];      // ranks left out
  current: number | null; // rank playing
  playAll: boolean;
}

export const watch = createStore<WatchState>({ source: null, order: [], removed: [], current: null, playAll: false });

export function syncWatch() {
  const list = highlights.get().list;
  if (!list || watch.get().source === list) return;
  const order = list.clips.filter((c) => c.file).map((c) => c.rank);
  watch.set({ source: list, order, removed: [], current: order[0] ?? null, playAll: false });
}

export function setOrder(order: number[]) {
  watch.set({ order });
}

export function removeClip(rank: number) {
  watch.set((s) => {
    const order = s.order.filter((r) => r !== rank);
    const i = s.order.indexOf(rank);
    return {
      order,
      removed: [...s.removed, rank],
      current: s.current === rank ? (order[Math.min(i, order.length - 1)] ?? null) : s.current,
    };
  });
}

export function restoreAll() {
  watch.set((s) => ({ order: [...s.order, ...s.removed], removed: [] }));
}

export function play(rank: number, playAll?: boolean) {
  watch.set((s) => ({ current: rank, playAll: playAll ?? s.playAll }));
}

/** Move to the next clip; false at the end. */
export function step(delta: number): boolean {
  const { order, current } = watch.get();
  const i = current == null ? -1 : order.indexOf(current);
  const next = order[i + delta];
  if (next == null) return false;
  watch.set({ current: next });
  return true;
}

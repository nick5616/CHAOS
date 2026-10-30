import { useSyncExternalStore } from "react";

/** A tiny global store. `use(select)` re-renders when the selected value
 *  changes, so select existing fields rather than building new objects. */
export function createStore<T>(initial: T) {
  let state = initial;
  const listeners = new Set<() => void>();
  const subscribe = (fn: () => void) => {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  };
  return {
    get: () => state,
    set(update: Partial<T> | ((s: T) => Partial<T>)) {
      const patch = typeof update === "function" ? update(state) : update;
      state = { ...state, ...patch };
      listeners.forEach((fn) => fn());
    },
    use<S>(select: (s: T) => S): S {
      return useSyncExternalStore(subscribe, () => select(state));
    },
  };
}

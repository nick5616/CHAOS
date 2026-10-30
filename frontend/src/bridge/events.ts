import { useEffect, useRef } from "react";
import type { ChaosEvents } from "./types";

// Python sends events as CustomEvent("chaos", {detail: {name, payload}}) on window.

type Name = keyof ChaosEvents;

export function onChaos<K extends Name>(name: K, handler: (payload: ChaosEvents[K]) => void): () => void {
  const listener = (e: Event) => {
    const { detail } = e as CustomEvent<{ name: string; payload: ChaosEvents[K] }>;
    if (detail?.name === name) handler(detail.payload);
  };
  window.addEventListener("chaos", listener);
  return () => window.removeEventListener("chaos", listener);
}

/** Subscribe for the component's lifetime; the latest handler is always used. */
export function useChaosEvent<K extends Name>(name: K, handler: (payload: ChaosEvents[K]) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => onChaos(name, (p) => ref.current(p)), [name]);
}

export function dispatchChaos<K extends Name>(name: K, payload: ChaosEvents[K]) {
  window.dispatchEvent(new CustomEvent("chaos", { detail: { name, payload } }));
}

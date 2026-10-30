import type { ChaosApi } from "./types";

export * from "./types";
export { onChaos, useChaosEvent } from "./events";

declare global {
  interface Window {
    pywebview?: { api: ChaosApi };
  }
}

// `npm run dev:mock`, or ?mock in the URL, runs the UI in a normal browser
// against a fake host (bridge/mock.ts). Otherwise wait for pywebview.
export const usingMock =
  import.meta.env.VITE_MOCK === "1" || new URLSearchParams(location.search).has("mock");

let ready: Promise<ChaosApi> | undefined;

function getApi(): Promise<ChaosApi> {
  ready ??= usingMock
    ? import("./mock").then((m) => m.createMock())
    : new Promise((resolve) => {
        const done = () => resolve(window.pywebview!.api);
        if (window.pywebview?.api && "app_info" in window.pywebview.api) done();
        else window.addEventListener("pywebviewready", done, { once: true });
      });
  return ready;
}

/** Typed host API. Calls made before pywebview is ready wait for it. */
export const api = new Proxy({} as ChaosApi, {
  get:
    (_, method: string) =>
    async (...args: unknown[]) => {
      const host = (await getApi()) as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>;
      return host[method](...args);
    },
});

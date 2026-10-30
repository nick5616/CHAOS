import { createStore } from "../lib/store";

export type ScreenId = "clips" | "run" | "highlights" | "watch" | "settings";

/** `peek` brings the room behind the app into focus (the settings easter egg). */
export const nav = createStore<{ screen: ScreenId; peek: boolean }>({ screen: "clips", peek: false });

export const go = (screen: ScreenId) => nav.set({ screen, peek: false });

export const setPeek = (peek: boolean) => nav.set({ peek });

import type { ClipEvent, EventType, Highlight, KillDetails } from "../bridge";

/** Killfeed icons a kill can carry, in killfeed order: [details key, short, long]. */
export const KILL_FLAGS: [keyof KillDetails, string, string][] = [
  ["attackerBlind", "Blind", "While blind"],
  ["inAir", "Air", "In the air"],
  ["noScope", "No-scope", "No-scope"],
  ["throughSmoke", "Smoke", "Through smoke"],
  ["wallbang", "Wallbang", "Wallbang"],
  ["isHeadshot", "HS", "Headshot"],
];

export function killFlags(d: KillDetails, long = false): string[] {
  return KILL_FLAGS.filter(([k]) => d[k]).map(([, short, full]) => (long ? full : short));
}

export const EVENT_STYLE: Record<EventType, { label: string; color: string; text: string }> = {
  kill: { label: "Kill", color: "bg-accent", text: "text-accent" },
  voice: { label: "Voice", color: "bg-secondary-hi", text: "text-secondary-hi" },
  chat: { label: "Chat", color: "bg-bad", text: "text-bad" },
  laughter: { label: "Laugh", color: "bg-warn", text: "text-warn" },
  audio_spike: { label: "Crowd", color: "bg-crowd", text: "text-crowd" },
};

export function describe(ev: ClipEvent): string {
  const d = ev.details;
  switch (ev.type) {
    case "kill": {
      const killer = d.inferred_player || d.detected_player;
      const flags = killFlags(d, true);
      return `${killer ? `${killer} killed ` : "Killed "}${d.victim ?? "someone"}${flags.length ? ` (${flags.join(", ").toLowerCase()})` : ""}`;
    }
    case "voice":
      return `“${d.text}”`;
    case "chat":
      return `Chat: “${d.text}”`;
    case "laughter":
      return "Laughter";
    case "audio_spike":
      return "Loud reaction";
  }
}

const TAG_LABELS: Record<string, string> = {
  "multi-kill": "Multi-kill",
  loud_reaction: "Loud reaction",
  running_bit: "Running bit",
  through_smoke: "Through smoke",
  no_scope: "No-scope",
};

export function tagLabel(tag: string): string {
  return TAG_LABELS[tag] ?? tag.replace(/[_-]/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export const KIND_LABEL: Record<Highlight["kind"], string> = {
  kill: "Kills",
  funny: "Funny",
  conversation: "Banter",
};

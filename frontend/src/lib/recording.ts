const TITLE = /(\d{4})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})\.(\d{2})/;
const FMT = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "Thu 29 Oct, 00:33" from a ShadowPlay name like
 *  "Counter-strike 2 2026.10.29 - 00.33.19.09.DVR.mp4"; else the bare name. */
export function recordingLabel(name: string): string {
  const m = name.match(TITLE);
  if (!m) return name.replace(/\.[^.]+$/, "");
  const [, y, mo, d, h, mi, s] = m.map(Number);
  return FMT.format(new Date(y, mo - 1, d, h, mi, s));
}

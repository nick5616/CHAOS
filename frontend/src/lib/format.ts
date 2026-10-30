const MB = 1 << 20;

/** "142 MB", "1.4 GB" */
export function fmtSize(bytes: number): string {
  const mb = bytes / MB;
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`;
  return `${Math.round(mb)} MB`;
}

/** "38.2 MB/s" */
export function fmtSpeed(bytesPerSec: number): string {
  return `${(bytesPerSec / MB).toFixed(1)} MB/s`;
}

/** "about 12 s left", "about 3 min left" */
export function fmtEta(sec: number | null | undefined): string {
  if (sec == null || !isFinite(sec)) return "";
  if (sec < 5) return "a few seconds left";
  if (sec < 60) return `about ${Math.ceil(sec / 5) * 5} s left`;
  const min = Math.round(sec / 60);
  return `about ${min} min left`;
}

/** "4:07", "1:02:33" */
export function fmtClock(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** "812 GB", "3.4 GB", "640 MB" (decimal units, like Explorer's drive view). */
export function fmtBytes(bytes: number): string {
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`;
  if (bytes >= 1e10) return `${Math.round(bytes / 1e9)} GB`;
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  return `${Math.round(bytes / 1e6)} MB`;
}

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Check, FolderOpen, FolderSearch, Search } from "lucide-react";
import type { Video } from "../bridge";
import { api } from "../bridge";
import { Button, Label } from "../components/ui";
import { cn } from "../lib/cn";
import { createStore } from "../lib/store";
import { fmtBytes, fmtClock } from "../lib/format";
import { chooseCapturesFolder, clips, setIncluded, wantThumb } from "../state/clips";
import { go } from "../state/nav";

const PREVIEW_SPEED = 10;   // seconds of video per second of preview
const STEP_MS = 100;        // one seek every STEP_MS
const ZOOM = 4;             // magnifier zoom over the full-resolution frame

// What the mouse is over, shared with the magnifier.
// `left` says the card is on the left half, so the magnifier docks on the right.
const hover = createStore<{ path: string | null; x: number; y: number; left: boolean }>({ path: null, x: 0.5, y: 0.5, left: true });
const hoverMedia: { video: HTMLVideoElement | null; img: HTMLImageElement | null } = { video: null, img: null };

export function ClipsScreen() {
  const status = clips.use((s) => s.status);
  const folder = clips.use((s) => s.folder);
  const exists = clips.use((s) => s.exists);
  const videos = clips.use((s) => s.videos);

  return (
    <div className="relative flex h-full flex-col">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 px-10 pb-5 pt-8">
        <div className="min-w-0">
          <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">Clips</h1>
          <p className="mt-2 text-[15px] text-fg-muted">
            Pick which recordings to scan. Hover one to preview it at 10x, click to leave it out.
          </p>
        </div>
        {exists && <FolderBar folder={folder} />}
      </div>

      {status !== "ready" ? (
        <div className="grid flex-1 place-items-center text-fg-faint">
          <div className="display animate-pulse text-[15px] tracking-[0.12em]">Loading recordings</div>
        </div>
      ) : !folder || !exists ? (
        <NoFolder missing={!!folder && !exists} folder={folder} />
      ) : videos.length === 0 ? (
        <Empty title="No recordings in this folder" body="CHAOS looks for .mp4, .mkv, .mov and .avi files directly inside it." />
      ) : (
        <>
          <Library videos={videos} />
          <ActionBar />
          <Magnifier />
        </>
      )}
    </div>
  );
}

function FolderBar({ folder }: { folder: string }) {
  return (
    <div className="ml-auto flex min-w-0 items-center gap-2">
      <div className="flex h-10 min-w-0 items-center gap-2.5 border border-line bg-black/30 px-3 text-[14px] text-fg-muted backdrop-blur-md">
        <FolderOpen className="size-4 shrink-0 text-fg-faint" />
        <span className="truncate" title={folder}>
          {folder}
        </span>
      </div>
      <Button onClick={() => void chooseCapturesFolder()}>Change</Button>
      <Button variant="ghost" onClick={() => void api.open_captures_folder()} title="Open in Explorer">
        Open
      </Button>
    </div>
  );
}

function NoFolder({ missing, folder }: { missing: boolean; folder: string }) {
  return (
    <Empty
      icon={<FolderSearch className="size-6 text-accent" />}
      title={missing ? "Can't find your captures folder" : "Where are your recordings?"}
      body={
        missing
          ? `${folder} doesn't exist any more. Point CHAOS at the folder your recorder saves to.`
          : "Point CHAOS at the folder your recorder (ShadowPlay, OBS...) saves CS2 videos to."
      }
      action={
        <Button variant="primary" onClick={() => void chooseCapturesFolder()}>
          Choose folder
        </Button>
      }
    />
  );
}

function Empty({ icon, title, body, action }: { icon?: React.ReactNode; title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="grid flex-1 place-items-center px-10 pb-16">
      <div className="flex max-w-[420px] flex-col items-center border border-line bg-panel/70 px-10 py-9 text-center backdrop-blur-xl">
        {icon && <div className="mb-4 grid size-12 place-items-center border border-accent/40 bg-accent/10">{icon}</div>}
        <div className="display text-[22px] font-bold">{title}</div>
        <p className="mt-2 text-[14.5px] leading-relaxed text-fg-muted">{body}</p>
        {action && <div className="mt-6">{action}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- library

interface Day {
  key: string;
  label: string;
  videos: Video[];
}

const DAY_FMT = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const DAY_FMT_YEAR = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });

function groupByDay(videos: Video[]): Day[] {
  const days: Day[] = [];
  const thisYear = new Date().getFullYear();
  for (const v of videos) {
    const key = v.recorded.slice(0, 10);
    let day = days[days.length - 1];
    if (!day || day.key !== key) {
      const d = new Date(v.recorded);
      day = { key, label: (d.getFullYear() === thisYear ? DAY_FMT : DAY_FMT_YEAR).format(d), videos: [] };
      days.push(day);
    }
    day.videos.push(v);
  }
  return days;
}

function Library({ videos }: { videos: Video[] }) {
  const [query, setQuery] = useState("");
  const days = useMemo(() => {
    const q = query.trim().toLowerCase();
    return groupByDay(q ? videos.filter((v) => v.name.toLowerCase().includes(q)) : videos);
  }, [videos, query]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-10 pb-32" onMouseLeave={() => hover.set({ path: null })}>
      <div className="sticky top-0 z-10 -mx-10 mb-1 flex items-center gap-3 bg-gradient-to-b from-bg via-bg/90 to-transparent px-10 pb-4 pt-1">
        <div className="flex h-9 w-72 items-center gap-2 border border-line bg-black/30 px-3 focus-within:border-accent/60">
          <Search className="size-4 text-fg-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name or date, e.g. 2026.10"
            className="min-w-0 flex-1 bg-transparent text-[14px] outline-none"
          />
        </div>
        <BulkButtons videos={videos} />
      </div>
      {days.map((day) => (
        <DaySection key={day.key} day={day} />
      ))}
      {days.length === 0 && <div className="py-16 text-center text-fg-faint">Nothing matches “{query}”.</div>}
    </div>
  );
}

function BulkButtons({ videos }: { videos: Video[] }) {
  const all = useMemo(() => videos.map((v) => v.path), [videos]);
  return (
    <div className="ml-auto flex gap-1">
      <Button size="sm" variant="ghost" onClick={() => setIncluded(all, true)}>
        Include all
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setIncluded(all, false)}>
        Leave all out
      </Button>
    </div>
  );
}

function DaySection({ day }: { day: Day }) {
  const paths = useMemo(() => day.videos.map((v) => v.path), [day]);
  const included = clips.use((s) => paths.reduce((n, p) => n + (s.excluded[p] ? 0 : 1), 0));
  const size = useMemo(() => day.videos.reduce((n, v) => n + v.size, 0), [day]);
  const allIn = included === paths.length;
  return (
    <section className="mb-8" style={{ contentVisibility: "auto", containIntrinsicSize: `auto ${Math.ceil(day.videos.length / 5) * 190 + 50}px` }}>
      <header className="mb-3 flex items-center gap-4 border-b border-line pb-2">
        <h2 className="display text-[20px] font-bold tracking-[0.06em]">{day.label}</h2>
        <span className="text-[13.5px] text-fg-faint tabular">
          {included === paths.length ? `${paths.length} recording${paths.length === 1 ? "" : "s"}` : `${included} of ${paths.length} included`}
          {" · "}
          {fmtBytes(size)}
        </span>
        <button
          onClick={() => setIncluded(paths, !allIn)}
          className="display ml-auto text-[13px] font-semibold tracking-[0.1em] text-fg-faint transition hover:text-accent"
        >
          {allIn ? "Leave out day" : "Include day"}
        </button>
      </header>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(236px,1fr))] gap-3">
        {day.videos.map((v) => (
          <VideoCard key={v.path} video={v} />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- cards

const observer =
  typeof IntersectionObserver !== "undefined"
    ? new IntersectionObserver(
        (entries) => {
          for (const e of entries)
            if (e.isIntersecting) {
              wantThumb((e.target as HTMLElement).dataset.path!);
              observer!.unobserve(e.target);
            }
        },
        { rootMargin: "400px 0px" },
      )
    : null;

const TIME_FMT = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

const VideoCard = memo(function VideoCard({ video }: { video: Video }) {
  const thumb = clips.use((s) => s.thumbs[video.path]);
  const excluded = clips.use((s) => !!s.excluded[video.path]);
  const hovered = hover.use((s) => s.path === video.path);
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !observer) return;
    observer.observe(el);
    return () => observer.unobserve(el);
  }, []);

  const onMove = (e: React.MouseEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    hover.set({
      path: video.path,
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
      left: r.left + r.width / 2 < window.innerWidth / 2,
    });
  };

  return (
    <button
      ref={ref}
      data-path={video.path}
      onClick={() => setIncluded([video.path], excluded)}
      className={cn(
        "group relative text-left outline-offset-0 transition",
        excluded ? "opacity-45 hover:opacity-80" : "",
      )}
      title={video.name}
    >
      <div
        className={cn(
          "relative aspect-video overflow-hidden border bg-raised transition-colors",
          excluded ? "border-line grayscale" : "border-line-strong group-hover:border-accent/70",
        )}
        onMouseMove={onMove}
        onMouseEnter={onMove}
        onMouseLeave={() => hover.get().path === video.path && hover.set({ path: null })}
      >
        {thumb?.url ? (
          <img
            src={thumb.url}
            ref={hovered ? (el) => void (hoverMedia.img = el) : undefined}
            className="size-full object-cover"
            draggable={false}
            alt=""
          />
        ) : thumb ? (
          <div className="grid size-full place-items-center text-[13px] text-fg-faint">Can&apos;t read this file</div>
        ) : (
          <div className="size-full animate-pulse bg-gradient-to-br from-raised to-hover" />
        )}
        {hovered && !excluded && <HoverPreview video={video} />}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-12 bg-gradient-to-b from-black/60 to-transparent" />
        <span
          className={cn(
            "absolute left-2 top-2 grid size-5 place-items-center border transition",
            excluded ? "border-white/40 bg-black/40" : "border-accent bg-accent text-accent-ink",
          )}
        >
          {!excluded && <Check className="size-3.5" strokeWidth={3.5} />}
        </span>
        {thumb?.duration ? (
          <span className="absolute bottom-1.5 right-1.5 bg-black/75 px-1.5 py-px font-mono text-[11.5px] text-white/90">
            {fmtClock(thumb.duration)}
          </span>
        ) : null}
        {excluded && (
          <span className="display absolute inset-0 grid place-items-center text-[15px] font-bold tracking-[0.16em] text-white/80">
            Left out
          </span>
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between px-0.5 text-[13.5px] text-fg-muted">
        <span className="truncate pr-2">{cardLabel(video)}</span>
        <span className="shrink-0 text-fg-faint tabular">{fmtBytes(video.size)}</span>
      </div>
    </button>
  );
});

/** The time of day for recorder-named files (the day is the section
 *  header); the file name for anything else. */
function cardLabel(video: Video): string {
  return /\d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}/.test(video.name)
    ? TIME_FMT.format(new Date(video.recorded))
    : video.name.replace(/\.[^.]+$/, "");
}

/** Steps through the video at 10x by seeking, so load stays steady no
 *  matter the resolution. Shows a progress line and the zoom area. */
function HoverPreview({ video }: { video: Video }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [progress, setProgress] = useState(0);
  const [live, setLive] = useState(false);
  const x = hover.use((s) => s.x);
  const y = hover.use((s) => s.y);

  useEffect(() => {
    const v = ref.current!;
    hoverMedia.video = v;
    let timer: number | undefined;
    let stopped = false;
    let last = 0;
    const step = () => {
      if (stopped || !v.duration) return;
      let t = v.currentTime + (PREVIEW_SPEED * STEP_MS) / 1000;
      if (t >= v.duration - 0.5) t = 0;
      last = performance.now();
      v.currentTime = t;
    };
    const onSeeked = () => {
      setLive(true);
      setProgress(v.currentTime / v.duration);
      timer = window.setTimeout(step, Math.max(0, STEP_MS - (performance.now() - last)));
    };
    const onMeta = () => {
      v.currentTime = Math.min(4, v.duration / 10);
    };
    // A short beat first, so sweeping the mouse across the grid doesn't
    // start a decode on every card it passes.
    const start = window.setTimeout(() => {
      v.src = video.url;
    }, 180);
    v.addEventListener("loadedmetadata", onMeta);
    v.addEventListener("seeked", onSeeked);
    return () => {
      stopped = true;
      clearTimeout(start);
      clearTimeout(timer);
      v.removeEventListener("loadedmetadata", onMeta);
      v.removeEventListener("seeked", onSeeked);
      v.removeAttribute("src");
      v.load();
      if (hoverMedia.video === v) hoverMedia.video = null;
    };
  }, [video.url]);

  const w = 1 / ZOOM;
  const left = Math.min(1 - w, Math.max(0, x - w / 2));
  const top = Math.min(1 - w, Math.max(0, y - w / 2));
  return (
    <>
      <video
        ref={ref}
        muted
        playsInline
        preload="auto"
        className={cn("absolute inset-0 size-full object-cover transition-opacity", live ? "opacity-100" : "opacity-0")}
      />
      <div
        className="pointer-events-none absolute border border-accent shadow-[0_0_0_9999px_rgba(0,0,0,0.25)]"
        style={{ left: `${left * 100}%`, top: `${top * 100}%`, width: `${w * 100}%`, height: `${w * 100}%` }}
      />
      <div className="absolute inset-x-0 bottom-0 h-[3px] bg-black/50">
        <div className="h-full bg-accent" style={{ width: `${progress * 100}%` }} />
      </div>
      <span className="display absolute bottom-2 left-2 bg-black/70 px-1.5 text-[12px] font-bold tracking-[0.1em] text-accent">
        {PREVIEW_SPEED}x
      </span>
    </>
  );
}

/** A docked zoom of the area under the cursor, drawn from the full-size
 *  preview frame, so the killfeed is readable. */
function Magnifier() {
  const path = hover.use((s) => s.path);
  const left = hover.use((s) => s.left);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!path) return;
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const c = canvas.current;
      const ctx = c?.getContext("2d");
      if (!c || !ctx) return;
      const v = hoverMedia.video;
      const src: CanvasImageSource | null = v && v.readyState >= 2 ? v : hoverMedia.img;
      if (!src) return;
      const sw0 = src instanceof HTMLVideoElement ? src.videoWidth : (src as HTMLImageElement).naturalWidth;
      const sh0 = src instanceof HTMLVideoElement ? src.videoHeight : (src as HTMLImageElement).naturalHeight;
      if (!sw0 || !sh0) return;
      const { x, y } = hover.get();
      const sw = sw0 / ZOOM;
      const sh = sh0 / ZOOM;
      const sx = Math.min(sw0 - sw, Math.max(0, x * sw0 - sw / 2));
      const sy = Math.min(sh0 - sh, Math.max(0, y * sh0 - sh / 2));
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(src, sx, sy, sw, sh, 0, 0, c.width, c.height);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [path]);

  return (
    <AnimatePresence>
      {path && (
        <motion.div
          className={cn(
            "pointer-events-none absolute bottom-24 z-20 border border-line-strong bg-black shadow-2xl shadow-black/70",
            left ? "right-8" : "left-8",
          )}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.15 }}
        >
          <canvas ref={canvas} width={640} height={360} className="block h-[202px] w-[360px]" />
          {/* scope corners */}
          {["left-1.5 top-1.5 border-l-2 border-t-2", "right-1.5 top-1.5 border-r-2 border-t-2", "left-1.5 bottom-1.5 border-l-2 border-b-2", "right-1.5 bottom-1.5 border-r-2 border-b-2"].map((c) => (
            <span key={c} className={cn("absolute size-3.5 border-accent", c)} />
          ))}
          <Label className="absolute left-3 top-2 text-white/70">{ZOOM}x zoom</Label>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------- action bar

function ActionBar() {
  const videos = clips.use((s) => s.videos);
  const excluded = clips.use((s) => s.excluded);
  const { count, size } = useMemo(() => {
    let count = 0;
    let size = 0;
    for (const v of videos)
      if (!excluded[v.path]) {
        count++;
        size += v.size;
      }
    return { count, size };
  }, [videos, excluded]);

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex items-end justify-end bg-gradient-to-t from-bg via-bg/80 to-transparent px-10 pb-6 pt-12">
      <div className="pointer-events-auto flex items-center gap-6">
        <div className="text-right">
          <div className="display text-[22px] font-bold leading-none tabular">
            {count} <span className="text-fg-faint">/ {videos.length}</span>
          </div>
          <div className="mt-1 text-[13px] text-fg-muted tabular">recordings included · {fmtBytes(size)}</div>
        </div>
        <Button variant="primary" size="lg" disabled={!count} onClick={() => go("run")}>
          Set up run <ArrowRight className="size-5" />
        </Button>
      </div>
    </div>
  );
}

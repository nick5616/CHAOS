import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import type { ClipEvent } from "../bridge";
import { cn } from "../lib/cn";
import { fmtClock } from "../lib/format";
import { EVENT_STYLE, describe, killFlags } from "../lib/events";

export interface PlayerHandle {
  seek(t: number, play?: boolean): void;
  toggle(): void;
  nudge(seconds: number): void;
}

const KILLFEED_HOLD = 4;    // seconds a kill stays in the overlay feed, like the game's
const MARKER_GAP = 1.4;     // % of the timeline two markers need before stacking

/** A clip with its events: a CS2-style killfeed and voice lines over the
 *  video, and the events marked on the scrubber. */
export function ClipPlayer({
  url,
  poster,
  events,
  playerRef,
  emptyText,
  autoPlay = false,
  onEnded,
  fill = false,
}: {
  url: string | null;
  poster?: string | null;
  events: ClipEvent[];
  playerRef?: Ref<PlayerHandle>;
  emptyText?: string;
  autoPlay?: boolean;
  onEnded?: () => void;
  /** Grow and shrink with the parent's height instead of a 16:9 box. */
  fill?: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);

  useImperativeHandle(playerRef, () => ({
    seek(t, play = true) {
      const v = video.current;
      if (!v) return;
      v.currentTime = Math.max(0, t);
      if (play) void v.play();
    },
    toggle() {
      const v = video.current;
      if (!v) return;
      if (v.paused) void v.play();
      else v.pause();
    },
    nudge(s) {
      const v = video.current;
      if (v) v.currentTime = Math.min(Math.max(0, v.currentTime + s), v.duration || 0);
    },
  }));

  useEffect(() => {
    setTime(0);
    setDuration(0);
    setPlaying(false);
  }, [url]);

  // Smooth time while playing (timeupdate only fires ~4 times a second).
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      if (video.current) setTime(video.current.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const kills = useMemo(() => events.filter((e) => e.type === "kill" && time >= e.t && time - e.t < KILLFEED_HOLD), [events, time]);
  const line = useMemo(
    () => events.find((e) => (e.type === "voice" || e.type === "chat") && time >= e.t && time <= (e.details.end ?? e.t + 2.2)),
    [events, time],
  );

  const toggle = () => {
    const v = video.current;
    if (!v || !url) return;
    if (v.paused) void v.play();
    else v.pause();
  };

  return (
    <div className={cn("flex flex-col border border-line bg-black", fill && "min-h-0 flex-1")}>
      <div
        className={cn("relative w-full overflow-hidden bg-black", fill ? "min-h-[160px] flex-1" : "aspect-video max-h-[52vh]")}
        onClick={toggle}
      >
        {url ? (
          <video
            key={url}
            ref={video}
            src={url}
            poster={poster ?? undefined}
            preload="auto"
            autoPlay={autoPlay}
            muted={muted}
            className="absolute inset-0 size-full object-contain"
            onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => {
              setPlaying(false);
              onEnded?.();
            }}
          />
        ) : (
          <>
            {poster && <img src={poster} alt="" className="size-full object-cover opacity-40 grayscale" />}
            <div className="absolute inset-0 grid place-items-center text-[15px] text-fg-muted">{emptyText ?? "No video"}</div>
          </>
        )}

        {/* our killfeed, top centre under the scoreboard (the game's own is top right) */}
        <div className="pointer-events-none absolute inset-x-0 top-[13%] flex flex-col items-center gap-1">
          <AnimatePresence initial={false}>
            {kills.map((k) => (
              <motion.div
                key={k.t}
                layout
                initial={{ opacity: 0, y: -8, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 border-2 border-[#e0302a] bg-black/65 px-2.5 py-1 text-[14px] font-semibold text-white shadow-lg"
              >
                <span className="text-[#ffd18a]">{k.details.inferred_player || k.details.detected_player || "You"}</span>
                {killFlags(k.details).map((f) => (
                  <span key={f} className="display bg-white/15 px-1 text-[11px] font-bold tracking-[0.08em] text-white/90">
                    {f}
                  </span>
                ))}
                <span>{k.details.victim ?? "?"}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* voice lines, as subtitles */}
        <AnimatePresence>
          {line && (
            <motion.div
              key={line.t}
              initial={{ opacity: 0, y: 6, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="pointer-events-none absolute inset-x-0 bottom-[9%] flex justify-center px-10"
            >
              <span className="max-w-[80%] text-center text-[clamp(16px,2.4vw,26px)] font-bold leading-tight text-white [text-shadow:0_2px_0_#000,0_0_10px_rgba(0,0,0,0.9),0_0_3px_#000]">
                {line.details.text}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {url && !playing && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="grid size-16 place-items-center bg-black/55 text-white backdrop-blur-sm">
              <Play className="ml-1 size-7 fill-current" />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 border-t border-line bg-panel px-3 py-2">
        <button onClick={toggle} disabled={!url} className="grid size-9 place-items-center text-fg transition hover:text-accent disabled:text-fg-faint" aria-label={playing ? "Pause" : "Play"}>
          {playing ? <Pause className="size-5 fill-current" /> : <Play className="size-5 fill-current" />}
        </button>
        <div className="w-[92px] shrink-0 font-mono text-[12.5px] text-fg-muted tabular">
          {fmtClock(time)} <span className="text-fg-faint">/ {fmtClock(duration)}</span>
        </div>
        <Timeline
          duration={duration}
          time={time}
          events={events}
          onSeek={(t) => {
            if (video.current) video.current.currentTime = t;
            setTime(t);
          }}
        />
        <button onClick={() => setMuted((m) => !m)} className="grid size-9 place-items-center text-fg-muted transition hover:text-fg" aria-label={muted ? "Unmute" : "Mute"}>
          {muted ? <VolumeX className="size-5" /> : <Volume2 className="size-5" />}
        </button>
      </div>
    </div>
  );
}

function Timeline({ duration, time, events, onSeek }: { duration: number; time: number; events: ClipEvent[]; onSeek: (t: number) => void }) {
  const track = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ x: number; ev?: ClipEvent } | null>(null);
  const dragging = useRef(false);

  // Stack markers that would overlap into up to three lanes.
  const markers = useMemo(() => {
    if (!duration) return [];
    const lanes: number[] = [];
    return events.map((ev) => {
      const x = Math.min(100, (ev.t / duration) * 100);
      let lane = lanes.findIndex((last) => x - last >= MARKER_GAP);
      if (lane === -1) lane = lanes.length < 3 ? lanes.length : 2;
      lanes[lane] = x;
      return { ev, x, lane };
    });
  }, [events, duration]);
  const laneCount = markers.reduce((n, m) => Math.max(n, m.lane + 1), 0);

  const tAt = (clientX: number) => {
    const r = track.current!.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * duration;
  };

  return (
    <div
      ref={track}
      className="relative min-w-0 flex-1 cursor-pointer select-none"
      style={{ height: 22 + laneCount * 9 }}
      onPointerDown={(e) => {
        if (!duration) return;
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        onSeek(tAt(e.clientX));
      }}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        setHover((h) => ({ x: e.clientX - r.left, ev: h?.ev }));
        if (dragging.current) onSeek(tAt(e.clientX));
      }}
      onPointerUp={() => (dragging.current = false)}
      onPointerLeave={() => setHover(null)}
    >
      {/* markers, lane 0 nearest the track */}
      {markers.map(({ ev, x, lane }, i) => (
        <span
          key={i}
          onPointerEnter={() => setHover((h) => ({ x: h?.x ?? 0, ev }))}
          onPointerLeave={() => setHover((h) => (h ? { x: h.x } : null))}
          onPointerDown={(e) => {
            e.stopPropagation();
            onSeek(Math.max(0, ev.t - 1));
          }}
          className={cn(
            "absolute -translate-x-1/2 transition-transform hover:scale-150",
            EVENT_STYLE[ev.type].color,
            ev.type === "kill" ? "size-[7px] rotate-45" : ev.type === "voice" ? "h-[7px] w-[3px]" : "size-[6px] rounded-full",
          )}
          style={{ left: `${x}%`, bottom: 14 + lane * 9 }}
        />
      ))}
      <div className="absolute inset-x-0 bottom-[5px] h-[4px] bg-white/10">
        <div className="h-full bg-accent" style={{ width: duration ? `${(time / duration) * 100}%` : 0 }} />
      </div>
      {duration > 0 && (
        <span className="absolute bottom-[2px] size-[10px] -translate-x-1/2 bg-fg shadow" style={{ left: `${(time / duration) * 100}%` }} />
      )}
      {hover && duration > 0 && (
        <div
          className="pointer-events-none absolute bottom-full z-10 mb-1 -translate-x-1/2 whitespace-nowrap border border-line-strong bg-panel px-2 py-1 text-[12.5px] shadow-xl"
          style={{ left: Math.min(Math.max(hover.x, 60), (track.current?.clientWidth ?? 0) - 60) }}
        >
          {hover.ev ? (
            <>
              <span className={cn("display mr-1.5 font-semibold tracking-[0.08em]", EVENT_STYLE[hover.ev.type].text)}>{EVENT_STYLE[hover.ev.type].label}</span>
              <span className="text-fg-muted">{fmtClock(hover.ev.t)}</span> {describe(hover.ev)}
            </>
          ) : (
            <span className="font-mono text-fg-muted">{fmtClock((hover.x / (track.current?.clientWidth || 1)) * duration)}</span>
          )}
        </div>
      )}
    </div>
  );
}

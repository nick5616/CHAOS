import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, Reorder } from "motion/react";
import { ArrowRight, Check, Clapperboard, Download, Pause, Play, RotateCcw, SkipBack, SkipForward, X } from "lucide-react";
import { api, useChaosEvent, type Highlight } from "../bridge";
import { ClipPlayer } from "../components/ClipPlayer";
import { Button } from "../components/ui";
import { cn } from "../lib/cn";
import { fmtClock } from "../lib/format";
import { KIND_LABEL } from "../lib/events";
import { clips, wantThumb } from "../state/clips";
import { highlights, loadHighlights } from "../state/highlights";
import { go } from "../state/nav";
import { play, removeClip, restoreAll, setOrder, step, syncWatch, watch } from "../state/watch";

export function WatchScreen() {
  const status = highlights.use((s) => s.status);
  const list = highlights.use((s) => s.list);
  const order = watch.use((s) => s.order);
  const removed = watch.use((s) => s.removed);
  const current = watch.use((s) => s.current);
  const playAll = watch.use((s) => s.playAll);

  useEffect(() => {
    void loadHighlights();
  }, []);
  useEffect(() => {
    syncWatch();
  }, [list]);

  const byRank = useMemo(() => new Map((list?.clips ?? []).map((c) => [c.rank, c])), [list]);
  const sequence = order.map((r) => byRank.get(r)).filter(Boolean) as Highlight[];
  const clip = current != null ? byRank.get(current) : undefined;
  const total = sequence.reduce((n, c) => n + c.length, 0);
  const index = clip ? sequence.indexOf(clip) : -1;
  const thumb = clips.use((s) => (clip?.file ? s.thumbs[clip.file]?.url : null));

  if (status !== "ready") return <div className="display grid h-full animate-pulse place-items-center text-fg-faint">Loading</div>;
  if (!byRank.size || (!sequence.length && !removed.length)) return <Nothing />;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 px-10 pb-4 pt-8">
        <div>
          <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">Watch</h1>
          <p className="mt-2 text-[15px] text-fg-muted">
            {sequence.length} clip{sequence.length === 1 ? "" : "s"} back to back · {fmtClock(total)}. Drag them into the order you want.
          </p>
        </div>
        <ExportButton paths={sequence.map((c) => c.file!)} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 px-10 pb-6">
        <div className="relative mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col">
          {clip ? (
            <>
              <ClipPlayer
                url={clip.url}
                poster={thumb}
                events={clip.events}
                autoPlay={playAll}
                fill
                onEnded={() => {
                  if (watch.get().playAll && !step(1)) watch.set({ playAll: false });
                }}
              />
              <div className="mt-2 flex shrink-0 items-center gap-3">
                <span className="display text-[17px] font-bold tracking-[0.04em]">
                  <span className="text-accent">#{clip.rank}</span> {clip.kind === "kill" ? `${clip.kills} kill${clip.kills === 1 ? "" : "s"}` : KIND_LABEL[clip.kind]}
                </span>
                <span className="text-[14px] text-fg-faint tabular">
                  {index + 1} of {sequence.length}
                </span>
                <div className="ml-auto flex items-center gap-1">
                  <Button size="sm" variant="ghost" disabled={index <= 0} onClick={() => step(-1)} aria-label="Previous clip">
                    <SkipBack className="size-4" />
                  </Button>
                  <Button size="sm" variant={playAll ? "secondary" : "primary"} onClick={() => watch.set({ playAll: !playAll })}>
                    {playAll ? <Pause className="size-4" /> : <Play className="size-4 fill-current" />}
                    {playAll ? "Stop playing all" : "Play all"}
                  </Button>
                  <Button size="sm" variant="ghost" disabled={index >= sequence.length - 1} onClick={() => step(1)} aria-label="Next clip">
                    <SkipForward className="size-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="grid flex-1 place-items-center text-fg-faint">Pick a clip below.</div>
          )}
        </div>

        <Strip sequence={sequence} current={current} removed={removed.length} />
      </div>
    </div>
  );
}

function Nothing() {
  return (
    <div className="grid h-full place-items-center px-10 pb-16">
      <div className="flex max-w-[420px] flex-col items-center border border-line bg-panel/70 px-10 py-9 text-center backdrop-blur-xl">
        <div className="mb-4 grid size-12 place-items-center border border-accent/40 bg-accent/10">
          <Clapperboard className="size-6 text-accent" />
        </div>
        <div className="display text-[22px] font-bold">Nothing to watch yet</div>
        <p className="mt-2 text-[14.5px] leading-relaxed text-fg-muted">Once a run finds some highlights, you can play them back to back here and export them as one video.</p>
        <Button variant="primary" className="mt-6" onClick={() => go("run")}>
          Go to Run <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

/** The sequence as a strip of cards; drag to reorder, tap to play. */
function Strip({ sequence, current, removed }: { sequence: Highlight[]; current: number | null; removed: number }) {
  return (
    <section className="shrink-0 border border-line bg-panel/75 backdrop-blur-xl">
      <header className="flex h-9 items-center justify-between border-b border-line px-3">
        <span className="display text-[13px] font-semibold tracking-[0.12em] text-fg-faint">Sequence</span>
        {removed > 0 && (
          <button onClick={restoreAll} className="display flex items-center gap-1.5 text-[12.5px] font-semibold tracking-[0.08em] text-fg-faint transition hover:text-accent">
            <RotateCcw className="size-3.5" /> Put back {removed} left out
          </button>
        )}
      </header>
      <div className="overflow-x-auto px-3 py-3">
        <Reorder.Group axis="x" values={sequence.map((c) => c.rank)} onReorder={setOrder} className="flex w-max gap-2">
          {sequence.map((c, i) => (
            <Card key={c.rank} clip={c} position={i + 1} active={c.rank === current} />
          ))}
        </Reorder.Group>
      </div>
    </section>
  );
}

function Card({ clip, position, active }: { clip: Highlight; position: number; active: boolean }) {
  const thumb = clips.use((s) => (clip.file ? s.thumbs[clip.file]?.url : null));
  useEffect(() => {
    if (clip.file) wantThumb(clip.file);
  }, [clip.file]);
  return (
    <Reorder.Item
      value={clip.rank}
      onTap={() => play(clip.rank)}
      whileDrag={{ scale: 1.06, zIndex: 10, boxShadow: "0 12px 30px rgba(0,0,0,0.6)" }}
      className={cn(
        "group relative w-[148px] shrink-0 cursor-grab border-2 bg-raised active:cursor-grabbing",
        active ? "border-accent" : "border-transparent hover:border-line-strong",
      )}
    >
      <div className="relative aspect-video overflow-hidden bg-black">
        {thumb && <img src={thumb} alt="" draggable={false} className="pointer-events-none size-full object-cover" />}
        <span className="display absolute left-1 top-0.5 text-[15px] font-bold text-white [text-shadow:0_1px_3px_#000]">{position}</span>
        <span className="absolute bottom-0.5 right-0.5 bg-black/75 px-1 font-mono text-[10.5px] text-white/90">{fmtClock(clip.length)}</span>
        {active && <span className="absolute inset-x-0 bottom-0 h-[3px] bg-accent" />}
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            removeClip(clip.rank);
          }}
          className="absolute right-0.5 top-0.5 hidden size-6 place-items-center bg-black/70 text-white/80 hover:text-bad group-hover:grid"
          aria-label="Leave out of the sequence"
          title="Leave out"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="flex items-center justify-between px-1.5 py-1 text-[12.5px]">
        <span className="truncate text-fg-muted">
          <span className={cn("font-semibold", clip.rank === 1 ? "text-accent" : "text-fg")}>#{clip.rank}</span>{" "}
          {clip.kind === "kill" ? `${clip.kills}K` : KIND_LABEL[clip.kind]}
        </span>
        <span className="text-fg-faint tabular">{clip.score}</span>
      </div>
    </Reorder.Item>
  );
}

function ExportButton({ paths }: { paths: string[] }) {
  const [state, setState] = useState<"idle" | "running" | "done" | "failed">("idle");
  const [fraction, setFraction] = useState(0);
  const [result, setResult] = useState<{ path: string; mode: string | null; message: string } | null>(null);

  useChaosEvent("export:progress", ({ fraction }) => setFraction(fraction));
  useChaosEvent("export:done", (r) => {
    setResult(r);
    setState(r.ok ? "done" : "failed");
  });

  const start = async () => {
    setFraction(0);
    setResult(null);
    if (await api.export_sequence(paths)) setState("running");
  };

  return (
    <div className="ml-auto flex items-center gap-3">
      <AnimatePresence mode="wait">
        {state === "running" && (
          <motion.div key="run" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="w-56">
            <div className="display flex justify-between text-[13px] font-semibold tracking-[0.1em]">
              <span className="text-accent">Exporting</span>
              <span className="tabular text-fg-muted">{Math.floor(fraction * 100)}%</span>
            </div>
            <div className="relative mt-1 h-1.5 overflow-hidden bg-white/10">
              <div className="relative h-full overflow-hidden bg-accent transition-[width] duration-150" style={{ width: `${fraction * 100}%` }}>
                <span className="stripes absolute inset-0" />
              </div>
            </div>
          </motion.div>
        )}
        {state === "done" && result && (
          <motion.div key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2 text-[14px]">
            <Check className="size-4 text-secondary-hi" />
            <span className="text-fg-muted">Saved{result.mode === "encode" ? " (re-encoded to one format)" : ""}</span>
            <Button size="sm" variant="ghost" onClick={() => void api.reveal_file(result.path)}>
              Show in folder
            </Button>
          </motion.div>
        )}
        {state === "failed" && result && (
          <motion.div key="fail" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="max-w-[380px] truncate text-[13.5px] text-bad" title={result.message}>
            Export failed: {result.message.split("\n").pop()}
          </motion.div>
        )}
      </AnimatePresence>
      <Button variant="primary" disabled={!paths.length || state === "running"} onClick={() => void start()}>
        <Download className="size-4" /> Export video
      </Button>
    </div>
  );
}

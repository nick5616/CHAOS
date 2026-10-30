import { memo, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, FolderOpen, RefreshCw, Sparkles } from "lucide-react";
import { api, type Highlight } from "../bridge";
import { ClipPlayer, type PlayerHandle } from "../components/ClipPlayer";
import { Button, Label, Panel } from "../components/ui";
import { cn } from "../lib/cn";
import { fmtBytes, fmtClock } from "../lib/format";
import { EVENT_STYLE, KIND_LABEL, describe, tagLabel } from "../lib/events";
import { recordingLabel } from "../lib/recording";
import { clips, wantThumb } from "../state/clips";
import { highlights, loadHighlights } from "../state/highlights";
import { go } from "../state/nav";

type Filter = "all" | Highlight["kind"];

export function HighlightsScreen() {
  const status = highlights.use((s) => s.status);
  const list = highlights.use((s) => s.list);
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    void loadHighlights();
  }, []);

  const all = list?.clips ?? [];
  const shown = useMemo(() => (filter === "all" ? all : all.filter((c) => c.kind === filter)), [all, filter]);
  const current = shown.find((c) => c.rank === selected) ?? shown[0] ?? null;
  const total = useMemo(() => all.reduce((n, c) => n + c.size, 0), [all]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 px-10 pb-5 pt-8">
        <div>
          <h1 className="display text-[34px] font-bold leading-none tracking-[0.04em]">Highlights</h1>
          <p className="mt-2 text-[15px] text-fg-muted">
            {all.length
              ? `${all.length} clip${all.length === 1 ? "" : "s"} from the last run, best first · ${fmtBytes(total)}`
              : "Your best moments, ranked, with every kill and laugh marked."}
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" onClick={() => void loadHighlights(true)} title="Reload">
            <RefreshCw className="size-4" /> Refresh
          </Button>
          <Button onClick={() => void api.open_clips_folder()}>
            <FolderOpen className="size-4" /> Clips folder
          </Button>
        </div>
      </div>

      {status !== "ready" ? (
        <div className="display grid flex-1 animate-pulse place-items-center pb-16 text-[15px] tracking-[0.12em] text-fg-faint">Loading</div>
      ) : !all.length ? (
        <NoHighlights />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(300px,380px)_1fr] gap-4 px-10 pb-8">
          <ClipList clips={all} shown={shown} filter={filter} setFilter={setFilter} current={current} onSelect={setSelected} />
          {current && <Detail key={current.rank} clip={current} shown={shown} onSelect={setSelected} />}
        </div>
      )}
    </div>
  );
}

function NoHighlights() {
  return (
    <div className="grid flex-1 place-items-center px-10 pb-16">
      <div className="flex max-w-[420px] flex-col items-center border border-line bg-panel/70 px-10 py-9 text-center backdrop-blur-xl">
        <div className="mb-4 grid size-12 place-items-center border border-accent/40 bg-accent/10">
          <Sparkles className="size-6 text-accent" />
        </div>
        <div className="display text-[22px] font-bold">No highlights yet</div>
        <p className="mt-2 text-[14.5px] leading-relaxed text-fg-muted">Run CHAOS on some recordings and your best moments show up here.</p>
        <Button variant="primary" className="mt-6" onClick={() => go("run")}>
          Go to Run <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the list

function ClipList({
  clips: all,
  shown,
  filter,
  setFilter,
  current,
  onSelect,
}: {
  clips: Highlight[];
  shown: Highlight[];
  filter: Filter;
  setFilter: (f: Filter) => void;
  current: Highlight | null;
  onSelect: (rank: number) => void;
}) {
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: all.length };
    for (const h of all) c[h.kind] = (c[h.kind] ?? 0) + 1;
    return c;
  }, [all]);
  const filters: Filter[] = ["all", "kill", "funny", "conversation"];
  const activeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [current?.rank]);

  return (
    <section className="flex min-h-0 flex-col border border-line bg-panel/75 backdrop-blur-xl">
      <div className="flex border-b border-line">
        {filters
          .filter((f) => f === "all" || counts[f])
          .map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "display relative flex-1 px-2 py-3 text-[14px] font-semibold tracking-[0.08em] transition-colors",
                filter === f ? "text-fg" : "text-fg-faint hover:text-fg",
              )}
            >
              {f === "all" ? "All" : KIND_LABEL[f]} <span className="text-fg-faint">{counts[f]}</span>
              {filter === f && <span className="absolute inset-x-3 bottom-0 h-[2px] bg-accent" />}
            </button>
          ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {shown.map((c) => (
          <Row key={c.rank} clip={c} active={c.rank === current?.rank} onClick={() => onSelect(c.rank)} innerRef={c.rank === current?.rank ? activeRef : undefined} />
        ))}
      </div>
    </section>
  );
}

const Row = memo(function Row({
  clip,
  active,
  onClick,
  innerRef,
}: {
  clip: Highlight;
  active: boolean;
  onClick: () => void;
  innerRef?: React.Ref<HTMLButtonElement>;
}) {
  const thumb = clips.use((s) => (clip.file ? s.thumbs[clip.file]?.url : null));
  useEffect(() => {
    if (clip.file) wantThumb(clip.file);
  }, [clip.file]);
  const top = clip.rank === 1;
  return (
    <button
      ref={innerRef}
      onClick={onClick}
      className={cn(
        "relative flex w-full items-center gap-3 border-b border-line px-3 py-2.5 text-left transition-colors",
        active ? "bg-white/[0.07]" : "hover:bg-white/[0.035]",
      )}
    >
      {active && <span className="absolute inset-y-0 left-0 w-[3px] bg-accent" />}
      <span className={cn("display w-8 shrink-0 text-center text-[22px] font-bold tabular", top ? "text-accent" : "text-fg-faint")}>{clip.rank}</span>
      <div className="relative aspect-video w-[104px] shrink-0 overflow-hidden border border-line bg-raised">
        {thumb && <img src={thumb} alt="" className={cn("size-full object-cover", !clip.file && "grayscale")} draggable={false} />}
        <span className="absolute bottom-0.5 right-0.5 bg-black/75 px-1 font-mono text-[10.5px] text-white/90">{fmtClock(clip.length)}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="display truncate text-[16px] font-semibold tracking-[0.04em]">
            {clip.kind === "kill" ? `${clip.kills} kill${clip.kills === 1 ? "" : "s"}` : KIND_LABEL[clip.kind]}
          </span>
          <span className={cn("display shrink-0 text-[15px] font-bold tabular", top ? "text-accent" : "text-fg-muted")}>{clip.score}</span>
        </div>
        <div className="truncate text-[13px] text-fg-faint">{recordingLabel(clip.source)}</div>
        {clip.tags.length > 0 && (
          <div className="mt-1 truncate text-[12px] text-fg-muted">{clip.tags.map(tagLabel).join(" · ")}</div>
        )}
      </div>
    </button>
  );
});

// ---------------------------------------------------------------- the clip

function Detail({ clip, shown, onSelect }: { clip: Highlight; shown: Highlight[]; onSelect: (rank: number) => void }) {
  const player = useRef<PlayerHandle>(null);
  const thumb = clips.use((s) => (clip.file ? s.thumbs[clip.file]?.url : null));

  // Space plays, arrows seek and move through the list.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      // Keys drive the player, so don't leave a focus ring on whatever was clicked last.
      if (e.target instanceof HTMLButtonElement) e.target.blur();
      const i = shown.findIndex((c) => c.rank === clip.rank);
      if (e.key === " ") player.current?.toggle();
      else if (e.key === "ArrowLeft") player.current?.nudge(-5);
      else if (e.key === "ArrowRight") player.current?.nudge(5);
      else if (e.key === "ArrowUp" && i > 0) onSelect(shown[i - 1].rank);
      else if (e.key === "ArrowDown" && i < shown.length - 1) onSelect(shown[i + 1].rank);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clip.rank, shown, onSelect]);

  return (
    <div className="flex min-h-0 flex-col">
      <ClipPlayer
        url={clip.url}
        poster={thumb}
        events={clip.events}
        playerRef={player}
        emptyText="This clip's file is gone from the clips folder."
      />

      <Panel className="mt-4 min-h-0 flex-1 overflow-y-auto" bodyClassName="p-0">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-line px-4 py-3.5">
          <Stat label="Rank" value={`#${clip.rank}`} accent={clip.rank === 1} />
          <Stat label="Score" value={String(clip.score)} />
          <Stat label="Length" value={fmtClock(clip.length)} />
          {clip.kind === "kill" && <Stat label="Kills" value={String(clip.kills)} />}
          <div className="min-w-[150px] flex-1">
            <Label>Recorded</Label>
            <div className="mt-0.5 truncate text-[15px]" title={clip.source}>
              {recordingLabel(clip.source)}
            </div>
          </div>
          {clip.file && (
            <Button size="sm" variant="ghost" onClick={() => void api.reveal_file(clip.file!)}>
              Show in folder
            </Button>
          )}
        </div>
        {clip.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-b border-line px-4 py-3">
            {clip.tags.map((t) => (
              <span key={t} className="display border border-line-strong bg-white/[0.04] px-2 py-0.5 text-[13px] font-semibold tracking-[0.06em] text-fg-muted">
                {tagLabel(t)}
              </span>
            ))}
          </div>
        )}
        <div className="px-1 py-1.5">
          {clip.events.length === 0 && <div className="px-3 py-2 text-[14px] text-fg-faint">No events recorded for this clip.</div>}
          {clip.events.map((ev, i) => (
            <button
              key={i}
              onClick={() => player.current?.seek(Math.max(0, ev.t - 1))}
              className="flex w-full items-baseline gap-3 px-3 py-1.5 text-left transition hover:bg-white/[0.05]"
              title="Jump here"
            >
              <span className="w-11 shrink-0 font-mono text-[12.5px] text-fg-faint tabular">{fmtClock(ev.t)}</span>
              <span className={cn("display w-14 shrink-0 text-[13px] font-semibold tracking-[0.08em]", EVENT_STYLE[ev.type].text)}>
                {EVENT_STYLE[ev.type].label}
              </span>
              <span className="min-w-0 flex-1 text-[14.5px] text-fg-muted">{describe(ev)}</span>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className={cn("display mt-0.5 text-[22px] font-bold leading-none tabular", accent && "text-accent")}>{value}</div>
    </div>
  );
}

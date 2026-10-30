import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { api, type Roi, type RoiFrame } from "../bridge";
import { Button, Label, Modal } from "./ui";
import { Slider } from "./Slider";
import { cn } from "../lib/cn";
import { recordingLabel } from "../lib/recording";

/** Killfeed regions for common resolutions, as [x1, y1, x2, y2] at [w, h]. */
export const PRESETS: { label: string; res: [number, number]; roi: Roi }[] = [
  { label: "1920×1080", res: [1920, 1080], roi: [1478, 30, 1900, 250] },
  { label: "2560×1440", res: [2560, 1440], roi: [1978, 40, 2540, 333] },
  { label: "3440×1440", res: [3440, 1440], roi: [2618, 40, 3420, 333] },
  { label: "2560×1080", res: [2560, 1080], roi: [2010, 30, 2540, 250] },
];

/** `roi` drawn at `from` resolution, moved to `to`. */
export function scaleRoi(roi: Roi, from: [number, number] | null, to: [number, number]): Roi {
  if (!from) return roi;
  const sx = to[0] / from[0];
  const sy = to[1] / from[1];
  return [Math.round(roi[0] * sx), Math.round(roi[1] * sy), Math.round(roi[2] * sx), Math.round(roi[3] * sy)];
}

/** The preset for this resolution, or the closest one with the same height, scaled to fit. */
export function presetFor(res: [number, number]): Roi {
  const exact = PRESETS.find((p) => p.res[0] === res[0] && p.res[1] === res[1]);
  if (exact) return exact.roi;
  // Killfeed is anchored top right: keep the same distance from the right edge.
  const base = PRESETS.reduce((a, p) => (Math.abs(p.res[1] - res[1]) < Math.abs(a.res[1] - res[1]) ? p : a));
  const s = res[1] / base.res[1];
  const right = (base.res[0] - base.roi[2]) * s;
  const w = (base.roi[2] - base.roi[0]) * s;
  return [Math.round(res[0] - right - w), Math.round(base.roi[1] * s), Math.round(res[0] - right), Math.round(base.roi[3] * s)];
}

type Drag = { mode: "move" | "nw" | "ne" | "sw" | "se" | "new"; x: number; y: number; start: Roi };

export function RegionEditor({
  open,
  roi,
  resolution,
  onClose,
  onSave,
}: {
  open: boolean;
  roi: Roi;
  resolution: [number, number] | null;
  onClose: () => void;
  onSave: (roi: Roi, resolution: [number, number]) => void;
}) {
  const [frame, setFrame] = useState<RoiFrame | null>(null);
  const [loading, setLoading] = useState(false);
  const [fraction, setFraction] = useState(0.35);
  const [box, setBox] = useState<Roi | null>(null);
  const area = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null);

  const load = async (index: number, f: number) => {
    setLoading(true);
    const next = await api.roi_frame(index, f);
    setLoading(false);
    if (!next) return;
    setFrame(next);
    setBox((b) => b ?? scaleRoi(roi, resolution, [next.width, next.height]));
  };

  useEffect(() => {
    if (!open) return;
    setBox(null);
    void load(0, 0.35);
  }, [open]);

  const toPx = (clientX: number, clientY: number) => {
    const r = area.current!.getBoundingClientRect();
    return [
      Math.round(((clientX - r.left) / r.width) * frame!.width),
      Math.round(((clientY - r.top) / r.height) * frame!.height),
    ];
  };

  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || !frame) return;
    const [x, y] = toPx(e.clientX, e.clientY);
    const dx = x - d.x;
    const dy = y - d.y;
    let [x1, y1, x2, y2] = d.start;
    const W = frame.width;
    const H = frame.height;
    if (d.mode === "move") {
      const w = x2 - x1;
      const h = y2 - y1;
      x1 = Math.min(W - w, Math.max(0, x1 + dx));
      y1 = Math.min(H - h, Math.max(0, y1 + dy));
      x2 = x1 + w;
      y2 = y1 + h;
    } else if (d.mode === "new") {
      [x1, x2] = [Math.min(d.x, x), Math.max(d.x, x)];
      [y1, y2] = [Math.min(d.y, y), Math.max(d.y, y)];
    } else {
      if (d.mode.includes("w")) x1 = Math.min(x2 - 20, x1 + dx);
      if (d.mode.includes("e")) x2 = Math.max(x1 + 20, x2 + dx);
      if (d.mode.includes("n")) y1 = Math.min(y2 - 20, y1 + dy);
      if (d.mode.includes("s")) y2 = Math.max(y1 + 20, y2 + dy);
    }
    setBox([Math.max(0, x1), Math.max(0, y1), Math.min(W, x2), Math.min(H, y2)]);
  };

  const start = (mode: Drag["mode"]) => (e: React.PointerEvent) => {
    if (!frame || !box) return;
    e.stopPropagation();
    area.current!.setPointerCapture(e.pointerId);
    const [x, y] = toPx(e.clientX, e.clientY);
    drag.current = { mode, x, y, start: box };
  };

  const pc = (v: number, of: number) => `${(v / of) * 100}%`;

  return (
    <Modal open={open} onClose={onClose} title="Killfeed region" width={1180}>
      <p className="-mt-1 mb-4 text-[14.5px] text-fg-muted">
        Drag the box over the killfeed (top right in CS2), or draw a new one. Pick a moment where some kills are showing so you can see
        it fits. CHAOS only reads inside this box.
      </p>
      <div className="flex gap-5">
        <div className="min-w-0 flex-1">
          <div
            ref={area}
            className="relative w-full cursor-crosshair touch-none select-none overflow-hidden border border-line-strong bg-black"
            style={{ aspectRatio: frame ? `${frame.width} / ${frame.height}` : "16 / 9" }}
            onPointerDown={start("new")}
            onPointerMove={onMove}
            onPointerUp={() => (drag.current = null)}
          >
            {frame && <img src={frame.url} alt="" draggable={false} className="pointer-events-none size-full" />}
            {loading && (
              <div className="absolute inset-0 grid place-items-center bg-black/40">
                <Loader2 className="size-7 animate-spin text-fg-muted" />
              </div>
            )}
            {frame && box && (
              <div
                className="absolute cursor-move border-2 border-accent bg-accent/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
                style={{ left: pc(box[0], frame.width), top: pc(box[1], frame.height), width: pc(box[2] - box[0], frame.width), height: pc(box[3] - box[1], frame.height) }}
                onPointerDown={start("move")}
              >
                {(["nw", "ne", "sw", "se"] as const).map((c) => (
                  <span
                    key={c}
                    onPointerDown={start(c)}
                    className={cn(
                      "absolute size-3.5 border-2 border-bg bg-accent",
                      c[0] === "n" ? "-top-2" : "-bottom-2",
                      c[1] === "w" ? "-left-2" : "-right-2",
                      c === "nw" || c === "se" ? "cursor-nwse-resize" : "cursor-nesw-resize",
                    )}
                  />
                ))}
                <span className="display absolute left-0 top-0 bg-accent px-1.5 text-[12px] font-bold tracking-[0.1em] text-accent-ink">Killfeed</span>
              </div>
            )}
          </div>
          {frame && (
            <div className="mt-3 flex items-center gap-3">
              <Button
                size="sm"
                variant="ghost"
                disabled={frame.index >= frame.count - 1 || loading}
                onClick={() => void load(frame.index + 1, fraction)}
                aria-label="Older recording"
              >
                <ChevronLeft className="size-4" />
              </Button>
              <div className="w-[170px] truncate text-[13.5px] text-fg-muted" title={frame.name}>
                {recordingLabel(frame.name)}
              </div>
              <Button size="sm" variant="ghost" disabled={frame.index === 0 || loading} onClick={() => void load(frame.index - 1, fraction)} aria-label="Newer recording">
                <ChevronRight className="size-4" />
              </Button>
              <Label className="ml-3 shrink-0">Moment</Label>
              <div className="flex flex-1" onPointerUp={() => void load(frame.index, fraction)} onKeyUp={() => void load(frame.index, fraction)}>
                <Slider label="Moment in the recording" value={fraction} min={0} max={1} step={0.01} onChange={setFraction} />
              </div>
            </div>
          )}
        </div>

        <div className="flex w-[260px] shrink-0 flex-col">
          <Label>Inside the box</Label>
          <div className="mt-2 aspect-[4/3] w-full overflow-hidden border border-line-strong bg-black">
            {frame && box && <Zoom frame={frame} box={box} />}
          </div>
          {frame && box && (
            <div className="mt-2 font-mono text-[12px] text-fg-faint tabular">
              {box[0]},{box[1]} → {box[2]},{box[3]} at {frame.width}×{frame.height}
            </div>
          )}
          <Label className="mt-5">Presets</Label>
          <div className="mt-2 grid grid-cols-2 gap-1.5">
            {PRESETS.map((p) => (
              <Button
                key={p.label}
                size="sm"
                variant={frame && p.res[0] === frame.width && p.res[1] === frame.height ? "secondary" : "ghost"}
                onClick={() => frame && setBox(scaleRoi(p.roi, p.res, [frame.width, frame.height]))}
                title={`Use the ${p.label} preset, scaled to this video`}
              >
                {p.label}
              </Button>
            ))}
          </div>
          <div className="mt-auto flex justify-end gap-2 pt-6">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!frame || !box} onClick={() => frame && box && onSave(box, [frame.width, frame.height])}>
              Use this region
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

/** What's inside the box, scaled to fit, so you can check it holds the whole killfeed. */
function Zoom({ frame, box }: { frame: RoiFrame; box: Roi }) {
  const w = box[2] - box[0];
  const h = box[3] - box[1];
  return (
    <svg viewBox={`${box[0]} ${box[1]} ${w} ${h}`} preserveAspectRatio="xMidYMid meet" className="size-full">
      <image href={frame.url} x={0} y={0} width={frame.width} height={frame.height} />
    </svg>
  );
}

/** A frame from the newest recording with the current region drawn on it. */
export function RegionPreview({ roi, resolution, onEdit }: { roi: Roi; resolution: [number, number] | null; onEdit: () => void }) {
  const [frame, setFrame] = useState<RoiFrame | null | undefined>(undefined);
  useEffect(() => {
    void api.roi_frame(0, 0.35).then(setFrame);
  }, []);
  if (frame === null)
    return <div className="text-[14px] text-fg-faint">Choose a captures folder with recordings to see the region on a real frame.</div>;
  const box = frame ? scaleRoi(roi, resolution, [frame.width, frame.height]) : null;
  const pc = (v: number, of: number) => `${(v / of) * 100}%`;
  return (
    <button onClick={onEdit} className="group relative block w-full overflow-hidden border border-line-strong bg-black" style={{ aspectRatio: frame ? `${frame.width} / ${frame.height}` : "16 / 9" }}>
      {frame && <img src={frame.url} alt="" className="size-full opacity-80 transition group-hover:opacity-100" draggable={false} />}
      {frame && box && (
        <span
          className="absolute border-2 border-accent shadow-[0_0_0_9999px_rgba(0,0,0,0.4)]"
          style={{ left: pc(box[0], frame.width), top: pc(box[1], frame.height), width: pc(box[2] - box[0], frame.width), height: pc(box[3] - box[1], frame.height) }}
        />
      )}
      <span className="display absolute bottom-2 left-2 bg-black/70 px-2 py-0.5 text-[13px] font-semibold tracking-[0.1em] text-fg opacity-0 transition group-hover:opacity-100">
        Edit region
      </span>
    </button>
  );
}

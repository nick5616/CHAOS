import { useRef } from "react";
import { cn } from "../lib/cn";

// Square-thumbed sliders in the CS2 settings style. Drag, click the track,
// or focus a thumb and use the arrow keys (Shift for bigger steps).

function useTrack(min: number, max: number, step: number) {
  const ref = useRef<HTMLDivElement>(null);
  const at = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    const raw = min + ((clientX - r.left) / r.width) * (max - min);
    return Math.min(max, Math.max(min, Math.round(raw / step) * step));
  };
  return { ref, at };
}

const pct = (v: number, min: number, max: number) => ((v - min) / (max - min)) * 100;

function keyStep(e: React.KeyboardEvent, step: number): number {
  const big = e.shiftKey ? 10 : 1;
  if (e.key === "ArrowRight" || e.key === "ArrowUp") return step * big;
  if (e.key === "ArrowLeft" || e.key === "ArrowDown") return -step * big;
  return 0;
}

const THUMB =
  "absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 border-2 border-bg bg-fg shadow-[0_0_0_1px_rgba(255,255,255,0.3)] outline-none transition-transform focus-visible:scale-125 focus-visible:bg-accent";

export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  label: string;
}) {
  const { ref, at } = useTrack(min, max, step);
  const clamp = (v: number) => Math.min(max, Math.max(min, +v.toFixed(4)));
  return (
    <div
      ref={ref}
      className="relative h-6 flex-1 cursor-pointer touch-none"
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        onChange(at(e.clientX));
      }}
      onPointerMove={(e) => e.buttons && onChange(at(e.clientX))}
    >
      <div className="absolute inset-x-0 top-1/2 h-[4px] -translate-y-1/2 bg-white/10">
        <div className="h-full bg-accent" style={{ width: `${pct(value, min, max)}%` }} />
      </div>
      <button
        role="slider"
        aria-label={label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        className={THUMB}
        style={{ left: `${pct(value, min, max)}%` }}
        onKeyDown={(e) => {
          const d = keyStep(e, step);
          if (d) {
            e.preventDefault();
            onChange(clamp(value + d));
          }
        }}
      />
    </div>
  );
}

/** Two thumbs, lo and hi. `track` is a CSS background for the rail. */
export function RangeSlider({
  value,
  min,
  max,
  step = 1,
  onChange,
  track,
  label,
}: {
  value: [number, number];
  min: number;
  max: number;
  step?: number;
  onChange: (v: [number, number]) => void;
  track?: string;
  label: string;
}) {
  const { ref, at } = useTrack(min, max, step);
  const active = useRef<0 | 1>(0);
  const [lo, hi] = value;
  const set = (which: 0 | 1, v: number) => {
    v = Math.min(max, Math.max(min, v));
    onChange(which === 0 ? [Math.min(v, hi), hi] : [lo, Math.max(v, lo)]);
  };
  return (
    <div
      ref={ref}
      className="relative h-7 flex-1 cursor-pointer touch-none"
      onPointerDown={(e) => {
        const v = at(e.clientX);
        active.current = Math.abs(v - lo) <= Math.abs(v - hi) ? 0 : 1;
        e.currentTarget.setPointerCapture(e.pointerId);
        set(active.current, v);
      }}
      onPointerMove={(e) => e.buttons && set(active.current, at(e.clientX))}
    >
      <div className="absolute inset-x-0 top-1/2 h-[10px] -translate-y-1/2 opacity-90" style={{ background: track ?? "rgb(255 255 255 / 0.1)" }}>
        {/* dim what's outside the range */}
        <div className="absolute inset-y-0 left-0 bg-bg/75" style={{ width: `${pct(lo, min, max)}%` }} />
        <div className="absolute inset-y-0 right-0 bg-bg/75" style={{ width: `${100 - pct(hi, min, max)}%` }} />
        <div className="absolute inset-y-0 border-y-2 border-white/70" style={{ left: `${pct(lo, min, max)}%`, right: `${100 - pct(hi, min, max)}%` }} />
      </div>
      {([0, 1] as const).map((w) => (
        <button
          key={w}
          role="slider"
          aria-label={`${label} ${w === 0 ? "from" : "to"}`}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value[w]}
          className={cn(THUMB, "h-5 w-2.5")}
          style={{ left: `${pct(value[w], min, max)}%` }}
          onKeyDown={(e) => {
            const d = keyStep(e, step);
            if (d) {
              e.preventDefault();
              set(w, value[w] + d);
            }
          }}
        />
      ))}
    </div>
  );
}

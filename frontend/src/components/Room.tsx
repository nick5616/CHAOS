import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  AnimatePresence,
  animate,
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";
import logo from "../assets/logo.png";
import { clips, wantThumb } from "../state/clips";
import { gpu, run, shortGpu } from "../state/run";
import type { ScreenId } from "../state/nav";
import "./room.css";

// The title room, after Black Ops: you're strapped in a chair facing a wall
// of CRTs. It's a CSS 3D scene, not WebGL: each monitor is a flat layer at a
// real depth, so the browser's perspective gives true parallax, and each
// layer blurs by its distance from wherever you're looking (depth of field).
// Normally ("screen" mode) it only sits behind the app, blurred and still
// except for a slight head turn with the mouse: an easter egg you'd recognise
// if you grew up on the game. Clicking the settings gear five times brings it
// into focus ("room" mode), where the mouse turns your head and WASD lets you
// strain against the straps. (Walking around would need a real 3D room: these
// layers are flat cut-outs that only look right from the chair.)

const STAGE_W = 1600;
const STAGE_H = 900;
const PERSPECTIVE = 1000;
const FOCUS_MAIN = -150;    // depth of the menu CRT
const FOCUS_RIGHT = -420;   // depth of the monitors on the right

export const MENU: { id: ScreenId; label: string; blurb: string }[] = [
  { id: "clips", label: "Clips", blurb: "Pick the recordings to scan" },
  { id: "run", label: "Run", blurb: "Find the highlights" },
  { id: "highlights", label: "Highlights", blurb: "Your best moments, ranked" },
  { id: "watch", label: "Watch", blurb: "Play them back to back" },
  { id: "settings", label: "Settings", blurb: "Folders, tuning, models" },
];

/** Where to put something so that, at depth `z`, it *looks* like it sits at
 *  (x, y, w, h) on the stage. Perspective shrinks far things toward the
 *  centre, so they're placed further out and drawn bigger. */
function place(x: number, y: number, w: number, h: number, z: number): CSSProperties {
  const k = (PERSPECTIVE - z) / PERSPECTIVE;
  return {
    left: STAGE_W / 2 + (x - STAGE_W / 2) * k,
    top: STAGE_H / 2 + (y - STAGE_H / 2) * k,
    width: w * k,
    height: h * k,
  };
}

export function Room({ mode, still = false, onPick }: { mode: "room" | "screen"; still?: boolean; onPick: (id: ScreenId) => void }) {
  // `still` is the "Background motion" setting turned off; it's treated like
  // the OS's reduce-motion setting: no head turn, sway, lean or focus shifts.
  const reduceOs = useReducedMotion();
  const reduce = reduceOs || still;
  const [scale, setScale] = useState(1);
  const [focus, setFocus] = useState<"main" | "right">("main");

  // Mouse, 0..1 across the window, smoothed like a slow, heavy head.
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const sx = useSpring(mx, { stiffness: 14, damping: 14, mass: 1.4 });
  const sy = useSpring(my, { stiffness: 14, damping: 14, mass: 1.4 });
  // 1 while the mouse is moving, easing back to 0 once it rests, so the room
  // goes still when you do.
  const moving = useMotionValue(0);
  const activity = useSpring(moving, { stiffness: 18, damping: 12 });
  const live = mode === "room";
  const [restrained, setRestrained] = useState(false);
  const reduceRef = useRef(reduce);
  reduceRef.current = reduce;
  useEffect(() => {
    if (reduce) setFocus("main");
  }, [reduce]);
  const amp = useSpring(reduce ? 0 : live ? 1 : 0.3, { stiffness: 60, damping: 20 });
  const dolly = useSpring(live ? 0 : 90, { stiffness: 50, damping: 18 });
  const focusZ = useSpring(FOCUS_MAIN, { stiffness: 70, damping: 20 });

  useEffect(() => {
    amp.set(reduce ? 0 : live ? 1 : 0.3);
    dolly.set(live ? 0 : 90);
  }, [live, reduce, amp, dolly]);

  useEffect(() => {
    focusZ.set(focus === "main" ? FOCUS_MAIN : FOCUS_RIGHT);
  }, [focus, focusZ]);

  useEffect(() => {
    let idle: number | undefined;
    const fit = () => setScale(Math.max(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H));
    const move = (e: MouseEvent) => {
      const x = e.clientX / window.innerWidth;
      mx.set(x);
      my.set(e.clientY / window.innerHeight);
      if (!reduceRef.current) setFocus(x > 0.6 ? "right" : "main");
      moving.set(1);
      clearTimeout(idle);
      idle = window.setTimeout(() => moving.set(0), 700);
    };
    fit();
    window.addEventListener("resize", fit);
    window.addEventListener("mousemove", move);
    return () => {
      clearTimeout(idle);
      window.removeEventListener("resize", fit);
      window.removeEventListener("mousemove", move);
    };
  }, [mx, my, moving]);

  // Breathing sway, only while the mouse moves and only in the room.
  const swayZ = useMotionValue(0);
  const swayY = useMotionValue(0);
  useAnimationFrame((t) => {
    // Below 2% it's invisible: stop outright rather than redraw for nothing.
    const a = live && !reduce ? activity.get() : 0;
    if (a < 0.02) {
      if (swayZ.get() !== 0) {
        swayZ.set(0);
        swayY.set(0);
      }
      return;
    }
    swayZ.set(Math.sin(t / 1300) * 0.3 * a);
    swayY.set(Math.sin(t / 1300 + 1.3) * 2 * a);
  });

  // WASD: lean against the straps; they pull you back when you let go. Mash
  // it and the chair jolts.
  const leanX = useSpring(0, { stiffness: 35, damping: 9 });
  const leanZ = useSpring(0, { stiffness: 35, damping: 9 });
  const jolt = useMotionValue(0);
  useEffect(() => {
    if (!live) return;
    const held = new Set<string>();
    let presses: number[] = [];
    let unrestrain: number | undefined;
    const lean = () => {
      if (reduce) return;
      leanX.set(((held.has("a") ? 1 : 0) - (held.has("d") ? 1 : 0)) * 70);
      leanZ.set((held.has("w") ? 110 : 0) - (held.has("s") ? 60 : 0));
    };
    const down = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (k.length !== 1 || !"wasd".includes(k)) return;
      held.add(k);
      lean();
      if (e.repeat) return;
      const now = Date.now();
      presses = [...presses.filter((t) => now - t < 3000), now];
      if (presses.length >= 10) {
        presses = [];
        if (!reduce) void animate(jolt, [0, 1.8, -1.4, 1, -0.5, 0], { duration: 0.6 });
        setRestrained(true);
        clearTimeout(unrestrain);
        unrestrain = window.setTimeout(() => setRestrained(false), 3500);
      }
    };
    const up = (e: KeyboardEvent) => {
      held.delete(e.key.toLowerCase());
      lean();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      clearTimeout(unrestrain);
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      leanX.set(0);
      leanZ.set(0);
    };
  }, [live, reduce, leanX, leanZ, jolt]);

  // Look toward the mouse, and roll a little in the corners.
  const rotateY = useTransform([sx, amp], ([x, a]: number[]) => (x - 0.5) * -9 * a);
  const rotateX = useTransform([sy, amp], ([y, a]: number[]) => (y - 0.5) * 6 * a);
  const rotateZ = useTransform([sx, sy, amp, jolt], ([x, y, a, j]: number[]) => (x - 0.5) * (0.5 - y) * 9 * a + j);
  const panX = useTransform([sx, amp, leanX], ([x, a, l]: number[]) => (x - 0.5) * -70 * a + l);
  const camZ = useTransform([dolly, leanZ], ([d, l]: number[]) => d + l);
  const panY = useTransform([sy, amp], ([y, a]: number[]) => (y - 0.5) * -40 * a);

  return (
    // Behind the app everything holds still (animations paused), so the blur
    // isn't redrawn every frame while you work or a run uses the GPU.
    <div className={`pointer-events-none fixed inset-0 overflow-hidden bg-black ${live ? "" : "room-paused"}`} aria-hidden={!live}>
      <motion.div
        className="absolute inset-0"
        initial={false}
        animate={{
          filter: live ? "blur(0px) brightness(1) saturate(1)" : "blur(11px) brightness(0.55) saturate(0.9)",
        }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="room-stage" style={{ transform: `scale(${scale})` }}>
          <motion.div className="room-3d" style={{ rotateZ: swayZ, y: swayY }}>
            <motion.div
              className="room-3d"
              style={{ x: panX, y: panY, z: camZ, rotateX, rotateY, rotateZ, transformOrigin: `50% 50% ${PERSPECTIVE}px` }}
            >
              <Scene focusZ={focusZ} live={live} restrained={restrained} onPick={onPick} />
            </motion.div>
          </motion.div>
        </div>
      </motion.div>
      <div className="room-vignette absolute inset-0" />
      <div className="room-grain absolute inset-0" />
    </div>
  );
}

/** One flat piece of the room at depth `z`, blurred by its distance from focus. */
function Layer({
  z,
  focusZ,
  style,
  className = "",
  sharp = 0,
  children,
  interactive,
  transform = "",
}: {
  z: number;
  focusZ: MotionValue<number>;
  style: CSSProperties;
  className?: string;
  /** Depth range that stays fully sharp around the focus. */
  sharp?: number;
  children?: ReactNode;
  interactive?: boolean;
  transform?: string;
}) {
  const filter = useTransform(focusZ, (f) => {
    const d = Math.max(0, Math.abs(z - f) - sharp);
    return `blur(${Math.min(14, d / 36).toFixed(2)}px)`;
  });
  return (
    <motion.div
      className={`room-layer ${className}`}
      style={{ ...style, filter, transform: `translateZ(${z}px) ${transform}`, pointerEvents: interactive ? "auto" : "none" }}
    >
      {children}
    </motion.div>
  );
}

function Scene({
  focusZ,
  live,
  restrained,
  onPick,
}: {
  focusZ: MotionValue<number>;
  live: boolean;
  restrained: boolean;
  onPick: (id: ScreenId) => void;
}) {
  const videos = clips.use((s) => s.videos);
  const thumbs = clips.use((s) => s.thumbs);
  const latest = useMemo(() => videos.slice(0, 8), [videos]);
  useEffect(() => {
    latest.forEach((v) => wantThumb(v.path));
  }, [latest]);
  const latestThumbs = latest.map((v) => thumbs[v.path]?.url).filter(Boolean) as string[];
  const interactive = live;

  return (
    <>
      {/* back wall and the red doorway */}
      <Layer z={-1300} focusZ={focusZ} style={place(-700, -500, 3000, 1900, -1300)} className="room-wall" />
      <Layer z={-1250} focusZ={focusZ} style={place(752, 330, 96, 270, -1250)} className="room-door" />

      {/* floor, leaning away from you */}
      <div
        className="room-layer room-floor"
        style={{ left: -1400, top: 760, width: 4400, height: 3200, transformOrigin: "50% 0", transform: "translateZ(260px) rotateX(-90deg)" }}
      />

      {/* the lamp and its light cone, with dust drifting in it */}
      <Layer z={-320} focusZ={focusZ} style={place(300, -40, 380, 900, -320)} className="room-cone" />
      <Layer z={-320} focusZ={focusZ} style={place(445, -70, 90, 90, -320)} className="room-bulb" />
      <Layer z={-300} focusZ={focusZ} style={place(330, 140, 320, 560, -300)}>
        {Array.from({ length: 16 }, (_, i) => (
          <span
            key={i}
            className="room-dust"
            style={
              {
                left: `${(i * 37) % 100}%`,
                top: `${30 + ((i * 53) % 70)}%`,
                animationDuration: `${7 + (i % 5) * 2}s`,
                animationDelay: `${-i * 1.3}s`,
                "--dx": `${((i % 3) - 1) * 30}px`,
              } as CSSProperties
            }
          />
        ))}
      </Layer>

      {/* right: wide screen up high, a CRT, and a console under it */}
      <Layer
        z={-560}
        focusZ={focusZ}
        sharp={90}
        style={place(1010, 120, 460, 170, -560)}
        transform="rotateY(-12deg)"
        interactive={interactive}
      >
        <WideScreen onPick={onPick} />
      </Layer>
      <Layer
        z={FOCUS_RIGHT}
        focusZ={focusZ}
        sharp={90}
        style={place(1050, 330, 320, 250, FOCUS_RIGHT)}
        transform="rotateY(-16deg)"
        interactive={interactive}
      >
        <ChannelCrt thumbs={latestThumbs} live={live} onClick={() => onPick("clips")} />
      </Layer>
      <Layer z={-400} focusZ={focusZ} sharp={90} style={place(1030, 600, 360, 140, -400)} transform="rotateY(-16deg)">
        <Console />
      </Layer>

      {/* left: the menu CRT on its stand, a terminal and a scope below */}
      <Layer
        z={FOCUS_MAIN}
        focusZ={focusZ}
        sharp={60}
        style={place(230, 160, 500, 480, FOCUS_MAIN)}
        transform="rotateY(14deg)"
        interactive={interactive}
      >
        <MenuCrt background={latestThumbs[0]} live={live} restrained={restrained} onPick={onPick} />
      </Layer>
      <Layer z={-110} focusZ={focusZ} sharp={60} style={place(250, 655, 180, 140, -110)} transform="rotateY(12deg)">
        <TerminalCrt restrained={restrained} />
      </Layer>
      <Layer z={-100} focusZ={focusZ} sharp={60} style={place(450, 690, 150, 105, -100)} transform="rotateY(10deg)">
        <Scope live={live} />
      </Layer>

      {/* the chair you're strapped into, close and out of focus */}
      <Layer z={240} focusZ={focusZ} style={place(-120, 820, 380, 260, 240)} transform="rotateZ(10deg)">
        <ChairArm side="left" />
      </Layer>
      <Layer z={240} focusZ={focusZ} style={place(1340, 820, 380, 260, 240)} transform="rotateZ(-10deg)">
        <ChairArm side="right" />
      </Layer>
    </>
  );
}

// ---------------------------------------------------------------- monitors

function MenuCrt({
  background,
  live,
  restrained,
  onPick,
}: {
  background?: string;
  live: boolean;
  restrained: boolean;
  onPick: (id: ScreenId) => void;
}) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!live) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") setActive((a) => (a + 1) % MENU.length);
      else if (e.key === "ArrowUp") setActive((a) => (a + MENU.length - 1) % MENU.length);
      else if (e.key === "Enter") onPick(MENU[active].id);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, live, onPick]);

  return (
    <div className="flex h-full flex-col">
      <div className="crt-cabinet relative flex h-[82%] items-stretch gap-[3%] p-[3.2%]">
        <Knobs />
        <div className="crt-screen crt-flicker relative flex-1">
          {restrained && (
            <div className="absolute inset-0 z-[5] grid place-items-center bg-[#050606]">
              <div className="crt-static absolute inset-0 opacity-[0.18]" />
              <div
                className="console-light relative text-center font-mono text-[34px] leading-tight font-bold text-[#ff5b4a] [text-shadow:0_0_14px_#ff3b2a]"
                style={{ "--d": "0.6s" } as CSSProperties}
              >
                SUBJECT
                <br />
                RESTRAINED
              </div>
            </div>
          )}
          {background && (
            <img src={background} alt="" className="absolute inset-0 size-full object-cover opacity-30 contrast-125 grayscale" />
          )}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.15),rgba(0,0,0,0.75))]" />
          <nav className="crt-glow relative z-[2] flex h-full flex-col justify-center px-[9%] text-[40px]">
            {MENU.map((item, i) => (
              <button
                key={item.id}
                className="crt-menu-item"
                data-active={i === active}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onClick={() => onPick(item.id)}
              >
                {item.label}
              </button>
            ))}
            <div className="mt-3 text-center font-sans text-[15px] tracking-[0.08em] text-[#b8c4bc] uppercase">{MENU[active].blurb}</div>
          </nav>
        </div>
        <Knobs />
        {/* the logo, stuck on like a sticker */}
        <img src={logo} alt="CHAOS" className="absolute -right-5 -top-7 w-[120px] rotate-[8deg] drop-shadow-[0_6px_8px_rgba(0,0,0,0.8)]" />
      </div>
      {/* stand */}
      <div className="relative mx-auto h-[18%] w-[70%]">
        <div className="absolute left-[8%] top-0 h-full w-[10px] bg-gradient-to-r from-[#6b6e70] via-[#3c3e40] to-[#1d1e1f]" />
        <div className="absolute right-[8%] top-0 h-full w-[10px] bg-gradient-to-r from-[#6b6e70] via-[#3c3e40] to-[#1d1e1f]" />
        <div className="absolute inset-x-[6%] top-[30%] h-[8px] bg-gradient-to-b from-[#55585a] to-[#1d1e1f]" />
      </div>
    </div>
  );
}

function Knobs() {
  return (
    <div className="flex w-[9%] flex-col items-center justify-center gap-[9%] rounded-[14px] bg-[#0f0e0d] py-[6%] shadow-[inset_0_0_14px_rgba(0,0,0,0.9)]">
      {[0, 1, 2, 3].map((i) => (
        <span key={i} className="crt-knob aspect-square w-[62%]" />
      ))}
    </div>
  );
}

/** Flips through your latest recordings like channels, with static between. */
function ChannelCrt({ thumbs, live, onClick }: { thumbs: string[]; live: boolean; onClick: () => void }) {
  const [i, setI] = useState(0);
  const [stat, setStat] = useState(false);
  useEffect(() => {
    if (thumbs.length < 2 || !live) return;
    const t = setInterval(() => {
      setStat(true);
      setTimeout(() => {
        setI((n) => (n + 1) % thumbs.length);
        setStat(false);
      }, 220);
    }, 3800);
    return () => clearInterval(t);
  }, [thumbs.length, live]);

  return (
    <button onClick={onClick} className="crt-cabinet group flex size-full flex-col p-[4%] text-left">
      <div className="crt-screen crt-flicker flex-1">
        {thumbs[i] ? (
          <motion.img
            key={thumbs[i]}
            src={thumbs[i]}
            alt=""
            className="absolute inset-0 size-full object-cover sepia-[0.25] saturate-[0.6]"
            initial={{ scale: 1.08 }}
            animate={{ scale: live ? 1.18 : 1.08 }}
            transition={{ duration: 4, ease: "linear" }}
          />
        ) : (
          <div className="crt-static absolute inset-0 opacity-40" />
        )}
        {stat && <div className="crt-static absolute inset-0 z-[2] opacity-80" />}
        <div className="crt-phosphor display absolute bottom-[7%] left-[8%] z-[2] text-[14px] font-semibold tracking-[0.14em] opacity-80 group-hover:opacity-100">
          Latest recordings ›
        </div>
      </div>
      <div className="mt-[3%] flex items-center justify-end gap-3 pr-[4%]">
        {[0, 1, 2].map((k) => (
          <span key={k} className="crt-knob size-[18px]" />
        ))}
      </div>
    </button>
  );
}

/** Up on the wall: what the pipeline is doing. */
function WideScreen({ onPick }: { onPick: (id: ScreenId) => void }) {
  const running = run.use((s) => s.running);
  const done = run.use((s) => s.done);
  const total = run.use((s) => s.total);
  const finished = run.use((s) => s.finished);
  return (
    <button
      onClick={() => onPick("run")}
      className="group relative size-full overflow-hidden border-[10px] border-[#121313] bg-[#d9efe9] shadow-[0_0_90px_rgba(180,240,230,0.3)]"
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_40%_40%,#ffffff,#cfe9e2_45%,#86a9a2)]" />
      <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,rgba(0,0,0,0.08)_0_1px,transparent_1px_3px)]" />
      <div className="relative flex h-full flex-col items-center justify-center text-[#18302b]">
        <AnimatePresence mode="wait">
          {running ? (
            <motion.div key="run" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center">
              <div className="display text-[26px] font-bold tracking-[0.2em]">Analyzing</div>
              <div className="display text-[56px] font-bold leading-none">
                {done}/{total}
              </div>
              <div className="mx-auto mt-3 h-2 w-[280px] bg-[#18302b]/20">
                <div className="h-full bg-[#18302b]" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
              </div>
            </motion.div>
          ) : (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center">
              <div className="display text-[46px] font-bold leading-none tracking-[0.12em]">{finished?.success ? "Done" : "Standing by"}</div>
              <div className="display mt-2 text-[18px] font-semibold tracking-[0.16em] opacity-70 group-hover:opacity-100">
                {finished?.success ? `${finished.clips} clips found ›` : "Run ›"}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </button>
  );
}

function TerminalCrt({ restrained }: { restrained: boolean }) {
  const count = clips.use((s) => s.videos.length);
  const info = gpu.use((s) => s.info);
  const running = run.use((s) => s.running);
  const gpuLine = !info ? "CHECKING" : info.cuda_available ? `${shortGpu(info.gpu_name)} OK` : info.gpu_present ? `${shortGpu(info.gpu_name)} OFF` : "CPU ONLY";
  return (
    <div className="crt-cabinet size-full p-[7%]">
      <div className="crt-screen size-full">
        {restrained ? (
          <div
            className="console-light relative z-[2] flex h-full flex-col items-center justify-center font-mono text-[15px] leading-tight font-bold text-[#ff5b4a] [text-shadow:0_0_8px_#ff3b2a]"
            style={{ "--d": "0.5s" } as CSSProperties}
          >
            <div>SUBJECT</div>
            <div>RESTRAINED</div>
          </div>
        ) : (
          <div className="crt-phosphor relative z-[2] flex h-full flex-col justify-center px-[12%] font-mono text-[12px] leading-[1.5]">
            <div>&gt; REC {count}</div>
            <div>&gt; GPU {gpuLine}</div>
            <div>
              &gt; RUN {running ? "ACTIVE" : "IDLE"}{" "}
              <span className="console-light" style={{ "--d": "1.06s" } as CSSProperties}>
                █
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** A little oscilloscope; the trace gets busier while a run is going. */
function Scope({ live }: { live: boolean }) {
  const running = run.use((s) => s.running);
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!live) return;
    let raf = 0;
    const tick = (now: number) => {
      setT(now / 1000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [live]);
  const points = useMemo(() => {
    const out: string[] = [];
    for (let x = 0; x <= 100; x += 2) {
      const a = running ? 14 : 6;
      const y = 30 + Math.sin(x / 6 + t * (running ? 9 : 3)) * a + (running ? Math.sin(x / 2.3 + t * 17) * 5 : 0);
      out.push(`${x},${y.toFixed(1)}`);
    }
    return out.join(" ");
  }, [t, running]);
  return (
    <div className="flex size-full flex-col rounded-[10px] bg-gradient-to-b from-[#3d3f37] to-[#22231f] p-[7%] shadow-[0_20px_40px_rgba(0,0,0,0.6)]">
      <div className="relative flex-1 overflow-hidden rounded-[6px] bg-[#0b1a0f] shadow-[inset_0_0_14px_#000]">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(125,255,155,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(125,255,155,0.12)_1px,transparent_1px)] bg-[size:20%_25%]" />
        <svg viewBox="0 0 100 60" preserveAspectRatio="none" className="absolute inset-0 size-full">
          <polyline points={points} fill="none" stroke="#7dff9b" strokeWidth="1.6" style={{ filter: "drop-shadow(0 0 2px #7dff9b)" }} />
        </svg>
      </div>
      <div className="mt-[6%] flex justify-between px-[4%]">
        {[0, 1, 2, 3].map((k) => (
          <span key={k} className="crt-knob size-[14px]" />
        ))}
      </div>
    </div>
  );
}

function Console() {
  const colors = ["#ff4b3a", "#7dff9b", "#ffd25a", "#e8f0ff"];
  return (
    <div className="size-full rounded-[6px] bg-gradient-to-b from-[#2b2e2f] to-[#121414] p-[4%] shadow-[0_30px_60px_rgba(0,0,0,0.7)]">
      <div className="grid h-[45%] grid-cols-12 gap-[6px]">
        {Array.from({ length: 24 }, (_, i) => (
          <span
            key={i}
            className="console-light rounded-[2px]"
            style={
              {
                background: colors[(i * 7) % colors.length],
                boxShadow: `0 0 8px ${colors[(i * 7) % colors.length]}`,
                "--d": `${1.2 + ((i * 13) % 9) / 4}s`,
                "--delay": `${-(i % 5) * 0.4}s`,
              } as CSSProperties
            }
          />
        ))}
      </div>
      <div className="mt-[5%] h-[30%] rounded-[3px] bg-[#0a0b0b] shadow-[inset_0_0_10px_#000]" />
    </div>
  );
}

function ChairArm({ side }: { side: "left" | "right" }) {
  return (
    <div className="chair-arm relative size-full">
      <div className={`chair-strap absolute top-[22%] h-[16%] w-[110%] ${side === "left" ? "-left-[5%]" : "-right-[5%]"}`} />
      <div className="absolute left-[44%] top-[24%] size-[34px] rounded-[3px] border-[5px] border-[#8a8172] bg-transparent" />
    </div>
  );
}

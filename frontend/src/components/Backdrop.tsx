import { motion } from "motion/react";

/** Ambient background for full-screen moments: a slow accent glow and a
 *  secondary one over a faint grid that fades out toward the edges. */
export function Backdrop({ intensity = 1 }: { intensity?: number }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(var(--color-line) 1px, transparent 1px), linear-gradient(90deg, var(--color-line) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 40%, black, transparent 75%)",
        }}
      />
      <motion.div
        className="absolute left-[5%] top-[-30%] h-[80%] w-[90%] rounded-full bg-accent blur-[140px]"
        animate={{ opacity: 0.11 * intensity, x: [-60, 60, -60], scale: [1, 1.08, 1] }}
        transition={{ opacity: { duration: 0.8 }, x: { duration: 18, repeat: Infinity, ease: "easeInOut" }, scale: { duration: 12, repeat: Infinity, ease: "easeInOut" } }}
      />
      <motion.div
        className="absolute bottom-[-40%] right-[-10%] h-[70%] w-[60%] rounded-full bg-secondary blur-[160px]"
        animate={{ opacity: [0.1, 0.16, 0.1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

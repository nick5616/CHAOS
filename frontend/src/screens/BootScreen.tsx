import { motion } from "motion/react";
import { Wordmark } from "../components/Wordmark";

/** Shown while the host checks which models are on disk. It fades in after a
 *  beat, so a fast check goes straight to the app with nothing flashing. */
export function BootScreen() {
  return (
    <motion.div
      className="grid h-full place-items-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1, transition: { delay: 0.35, duration: 0.5 } }}
      exit={{ opacity: 0, transition: { duration: 0.2 } }}
    >
      <motion.div animate={{ opacity: [0.7, 1, 0.7], scale: [1, 1.03, 1] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}>
        <Wordmark className="h-24" />
      </motion.div>
    </motion.div>
  );
}

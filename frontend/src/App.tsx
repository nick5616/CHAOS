import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, type ModelsStatus } from "./bridge";
import { BootScreen } from "./screens/BootScreen";
import { CheckFailed } from "./screens/CheckFailed";
import { ModelGate } from "./screens/ModelGate";
import { Shell } from "./components/Shell";

type Phase = { name: "boot" } | { name: "gate"; status: ModelsStatus } | { name: "failed"; message: string } | { name: "app" };

export default function App() {
  const [phase, setPhase] = useState<Phase>({ name: "boot" });

  useEffect(() => {
    let cancelled = false;
    api.models_status().then((status) => {
      if (cancelled) return;
      if (status.error) setPhase({ name: "failed", message: status.error });
      else if (status.models.some((m) => !m.ready)) setPhase({ name: "gate", status });
      else setPhase({ name: "app" });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AnimatePresence mode="wait">
      {phase.name === "boot" && <BootScreen key="boot" />}
      {phase.name === "gate" && (
        <motion.div key="gate" className="h-full" exit={{ opacity: 0, transition: { duration: 0.3 } }}>
          <ModelGate models={phase.status.models} onReady={() => setPhase({ name: "app" })} />
        </motion.div>
      )}
      {phase.name === "failed" && (
        <motion.div key="failed" className="h-full" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <CheckFailed message={phase.message} onContinue={() => setPhase({ name: "app" })} />
        </motion.div>
      )}
      {phase.name === "app" && (
        <motion.div
          key="app"
          className="h-full"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } }}
        >
          <Shell />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

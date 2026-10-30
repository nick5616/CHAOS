import { useEffect, useRef, useState } from "react";
import { Copy } from "lucide-react";
import { api, useChaosEvent } from "../bridge";
import { Button, Label, Modal } from "./ui";
import { gpu } from "../state/run";

export function CudaDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const info = gpu.use((s) => s.info);
  const [command, setCommand] = useState("");
  const [lines, setLines] = useState<string[]>([]);
  const [state, setState] = useState<"idle" | "installing" | "done" | "failed">("idle");
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (open && !command) void api.cuda_install_command().then(setCommand);
  }, [open, command]);
  useChaosEvent("cuda:output", ({ line }) => setLines((l) => [...l.slice(-400), line]));
  useChaosEvent("cuda:done", ({ success }) => setState(success ? "done" : "failed"));
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [lines]);

  const install = () => {
    setLines([]);
    setState("installing");
    void api.install_cuda();
  };

  return (
    <Modal open={open} onClose={onClose} title="Turn on GPU acceleration" width={600} dismissable={state !== "installing"}>
      <p className="text-[15px] leading-relaxed text-fg-muted">
        CHAOS found <span className="text-fg">{info?.gpu_name ?? "an NVIDIA GPU"}</span>
        {info?.driver_version && ` (driver ${info.driver_version})`}, but the installed PyTorch only runs on the processor. Installing the
        GPU build makes analysis up to 8x faster. It&apos;s about 2 to 3 GB and takes a few minutes.
      </p>

      {state !== "idle" && (
        <pre
          ref={logRef}
          className="mt-4 h-40 overflow-auto border border-line bg-black/40 p-3 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-fg-muted select-text"
        >
          {lines.join("\n") || "Starting…"}
        </pre>
      )}
      {state === "done" && <p className="mt-3 text-[14.5px] text-secondary-hi">Installed. Restart CHAOS to start using the GPU.</p>}
      {state === "failed" && <p className="mt-3 text-[14.5px] text-bad">The install failed. The log above says why, or run the command below yourself.</p>}

      <div className="mt-5 flex justify-end gap-2">
        {state === "done" ? (
          <Button variant="primary" onClick={() => void api.restart_app()}>
            Restart CHAOS
          </Button>
        ) : (
          <Button variant="primary" onClick={install} disabled={state === "installing"}>
            {state === "installing" ? "Installing…" : state === "failed" ? "Try again" : "Install GPU build"}
          </Button>
        )}
      </div>

      <div className="mt-5 border-t border-line pt-4">
        <Label>Or run it yourself</Label>
        <div className="mt-2 flex items-center gap-2">
          <code className="min-w-0 flex-1 truncate border border-line bg-black/30 px-3 py-2 font-mono text-[12px] text-fg-muted select-text" title={command}>
            {command}
          </code>
          <Button size="sm" variant="ghost" onClick={() => void navigator.clipboard.writeText(command)} title="Copy">
            <Copy className="size-4" />
          </Button>
        </div>
      </div>
    </Modal>
  );
}

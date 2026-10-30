import { AlertTriangle } from "lucide-react";

/** The model check itself crashed (usually a broken install). Say so, and let
 *  the user carry on: a run will report the same problem in its log. */
export function CheckFailed({ message, onContinue }: { message: string; onContinue: () => void }) {
  return (
    <div className="grid h-full place-items-center px-6">
      <div className="w-full max-w-[520px]">
        <AlertTriangle className="size-7 text-warn" />
        <h1 className="display mt-5 text-[30px] font-bold tracking-[0.04em]">CHAOS couldn&apos;t check its AI models</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-fg-muted">
          Running setup again usually fixes this. You can still look around, but a run will probably fail the same way.
        </p>
        <pre className="mt-5 max-h-40 overflow-auto rounded-xl border border-line bg-panel p-3.5 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-fg-muted select-text">
          {message}
        </pre>
        <button
          onClick={onContinue}
          className="mt-6 rounded-lg border border-line-strong bg-raised px-4 py-2 text-[14px] font-medium transition hover:bg-hover"
        >
          Continue anyway
        </button>
      </div>
    </div>
  );
}

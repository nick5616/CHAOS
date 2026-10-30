import logo from "../assets/logo.png";
import { cn } from "../lib/cn";

/** The hand-drawn CHAOS logo. Size it with a height class (h-10 etc.). */
export function Wordmark({ className }: { className?: string }) {
  return <img src={logo} alt="CHAOS" draggable={false} className={cn("w-auto select-none", className)} />;
}

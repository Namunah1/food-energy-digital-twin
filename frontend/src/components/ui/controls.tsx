import { cn } from "@/lib/utils";
import { HTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes } from "react";

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "teal" | "amber" | "crimson" | "azure" }) {
  const toneClasses: Record<string, string> = {
    neutral: "bg-panel-2 text-ink-2 border-hairline-2",
    teal: "bg-teal/10 text-teal border-teal/30",
    amber: "bg-amber/10 text-amber border-amber/30",
    crimson: "bg-crimson/10 text-crimson border-crimson/30",
    azure: "bg-azure/10 text-azure border-azure/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wider",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}

export function Slider({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="range"
      className={cn(
        "w-full h-1.5 rounded-full bg-hairline-2 appearance-none cursor-pointer accent-teal",
        "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-teal [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(63,199,190,0.6)]",
        className
      )}
      {...props}
    />
  );
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-sm text-ink-1 focus:outline-none focus:ring-1 focus:ring-teal/60 focus:border-teal/60",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

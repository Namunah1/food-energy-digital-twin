"use client";

import { Card } from "./ui/card";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export function MetricCard({
  label,
  value,
  unit,
  trend,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  unit?: string;
  trend?: "up" | "down" | "flat";
  tone?: "neutral" | "teal" | "amber" | "crimson";
  hint?: string;
}) {
  const toneClass = {
    neutral: "text-ink-1",
    teal: "text-teal",
    amber: "text-amber",
    crimson: "text-crimson",
  }[tone];

  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  return (
    <Card className="p-5 relative overflow-hidden group hover:border-hairline-2 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-mono uppercase tracking-widest text-ink-3">{label}</p>
        {trend && (
          <TrendIcon
            size={14}
            className={cn(
              trend === "up" && "text-crimson",
              trend === "down" && "text-teal",
              trend === "flat" && "text-ink-3"
            )}
          />
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className={cn("font-display text-3xl font-semibold tabular-nums", toneClass)}>{value}</span>
        {unit && <span className="text-sm text-ink-3 font-mono">{unit}</span>}
      </div>
      {hint && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
    </Card>
  );
}

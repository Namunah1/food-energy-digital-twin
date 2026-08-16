"use client";

import { useState, useEffect, useRef } from "react";
import { WorldMapClient } from "@/components/map/WorldMapClient";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/controls";
import { Play, Pause, RotateCcw, ChevronLeft, ChevronRight } from "lucide-react";
import type { SimulationSnapshot, MetricsRecord } from "@/lib/api";

export function TimelineReplay({
  snapshots,
  timeseries,
  height = 460,
}: {
  snapshots: SimulationSnapshot[];
  timeseries: MetricsRecord[];
  height?: number;
}) {
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setIdx((i) => {
          if (i >= snapshots.length - 1) {
            setPlaying(false);
            return i;
          }
          return i + 1;
        });
      }, 350);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, snapshots.length]);

  const snapshot = snapshots[idx];
  const metrics = timeseries[Math.max(0, idx - 1)];

  if (!snapshot) return null;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <Button size="sm" variant="ghost" onClick={() => { setPlaying(false); setIdx((i) => Math.max(0, i - 1)); }} disabled={idx === 0}>
          <ChevronLeft size={14} />
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setPlaying((p) => !p)} disabled={idx >= snapshots.length - 1 && !playing}>
          {playing ? <Pause size={14} /> : <Play size={14} />}
          {playing ? "Pause" : "Play"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => { setPlaying(false); setIdx((i) => Math.min(snapshots.length - 1, i + 1)); }} disabled={idx >= snapshots.length - 1}>
          <ChevronRight size={14} />
        </Button>
        <Button size="sm" variant="ghost" onClick={() => { setIdx(0); setPlaying(false); }}>
          <RotateCcw size={14} /> Reset
        </Button>
        <div className="ml-auto flex items-baseline gap-2">
          <span className="text-[10px] font-mono text-ink-3 uppercase tracking-wider">
            step {snapshot.step}/{snapshots.length - 1}
          </span>
          <span className="font-display text-2xl font-semibold text-ink-1 tabular-nums">{snapshot.year}</span>
        </div>
      </div>
      <Slider
        min={0}
        max={snapshots.length - 1}
        value={idx}
        onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)); }}
      />
      <div className="grid lg:grid-cols-[1fr_260px] gap-4 mt-4">
        <div className="relative rounded-xl overflow-hidden border border-hairline" style={{ height }}>
          <WorldMapClient nodes={snapshot.nodes} showEdges={false} />
        </div>
        {metrics && (
          <div className="space-y-2">
            <MiniMetric label="Global Food Security" value={metrics.GFS?.toFixed(2)} />
            <MiniMetric label="Price Index" value={metrics.price_index?.toFixed(2)} />
            <MiniMetric label="Population at Risk" value={`${(metrics.PAR_millions / 1000).toFixed(2)}bn`} />
            <MiniMetric label="Overloaded nodes" value={String(metrics.n_overload_food)} />
            <MiniMetric label="Trade collapse" value={metrics.TC_trade_collapse?.toFixed(2)} />
          </div>
        )}
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-panel-2 px-3 py-2">
      <p className="text-[10px] font-mono uppercase tracking-widest text-ink-3">{label}</p>
      <p className="font-display text-lg text-ink-1 mt-0.5">{value ?? "—"}</p>
    </div>
  );
}

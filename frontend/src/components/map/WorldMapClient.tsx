"use client";

import dynamic from "next/dynamic";
import type { NodeState, NetworkEdge } from "@/lib/api";

const WorldMapInner = dynamic(() => import("./WorldMap").then((m) => m.WorldMap), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 rounded-xl border border-hairline bg-panel flex items-center justify-center">
      <span className="text-ink-3 text-sm font-mono">Loading map…</span>
    </div>
  ),
});

export function WorldMapClient(props: {
  nodes: NodeState[];
  edges?: NetworkEdge[];
  onSelect?: (name: string) => void;
  selected?: string | null;
  showEdges?: boolean;
}) {
  return <WorldMapInner {...props} />;
}

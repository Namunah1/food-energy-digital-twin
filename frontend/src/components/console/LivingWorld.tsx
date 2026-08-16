"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { WorldMapClient } from "@/components/map/WorldMapClient";
import { api } from "@/lib/api";
import type { NodeState } from "@/lib/api";
import { Map, GitBranch, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function LivingWorld({
  nodes,
  onSelectCountry,
  selectedCountry,
}: {
  nodes: NodeState[];
  onSelectCountry?: (name: string) => void;
  selectedCountry?: string | null;
}) {
  const [view, setView] = useState<"map" | "network">("map");

  // Edge/trade-link data isn't part of an experiment snapshot, so it has to be
  // fetched separately. Only fetch it once the user actually switches to the
  // Network view (previously this was never fetched at all, so the toggle had
  // no effect and no edges were ever drawn).
  const { data: networkData, isLoading: edgesLoading } = useQuery({
    queryKey: ["living-world-network"],
    queryFn: () => api.network(10),
    enabled: view === "network",
    staleTime: 60_000,
  });

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-1 mb-2">
        <ToggleBtn active={view === "map"} onClick={() => setView("map")} icon={<Map size={13} />} label="Map" />
        <ToggleBtn active={view === "network"} onClick={() => setView("network")} icon={<GitBranch size={13} />} label="Network" />
        {view === "network" && edgesLoading && (
          <Loader2 size={12} className="animate-spin text-ink-3" />
        )}
        <span className="ml-auto text-[10px] font-mono text-ink-3">
          size = population &middot; color = food security
        </span>
      </div>
      <div className="flex-1 relative rounded-xl overflow-hidden border border-hairline min-h-[380px]">
        <WorldMapClient
          nodes={nodes}
          edges={networkData?.edges ?? []}
          showEdges={view === "network"}
          onSelect={onSelectCountry}
          selected={selectedCountry}
        />
      </div>
    </div>
  );
}

function ToggleBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-colors",
        active ? "border-teal/50 bg-teal/10 text-teal" : "border-transparent text-ink-3 hover:text-ink-1"
      )}
    >
      {icon} {label}
    </button>
  );
}

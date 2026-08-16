"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listExperiments, deleteExperiment } from "@/lib/api";
import { Badge } from "@/components/ui/controls";
import { X, Trash2, FlaskConical } from "lucide-react";

export function ExperimentDrawer({
  open,
  onClose,
  onOpenExperiment,
  currentId,
}: {
  open: boolean;
  onClose: () => void;
  onOpenExperiment: (id: string) => void;
  currentId?: string | null;
}) {
  const queryClient = useQueryClient();
  const { data: experiments } = useQuery({ queryKey: ["experiment-list"], queryFn: listExperiments, enabled: open });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-sm bg-panel border-l border-hairline h-full overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display text-lg font-semibold text-ink-1 flex items-center gap-2">
            <FlaskConical size={16} className="text-teal" /> My Experiments
          </h2>
          <button onClick={onClose} className="text-ink-3 hover:text-ink-1">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-2">
          {experiments?.length === 0 && <p className="text-xs text-ink-3 font-mono">No saved experiments yet.</p>}
          {experiments?.map((e) => (
            <div
              key={e.id}
              className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                e.id === currentId ? "border-teal/50 bg-teal/5" : "border-hairline-2 hover:border-hairline"
              }`}
              onClick={() => { onOpenExperiment(e.id); onClose(); }}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-ink-1 font-medium">{e.label}</p>
                <button
                  onClick={async (ev) => {
                    ev.stopPropagation();
                    await deleteExperiment(e.id);
                    queryClient.invalidateQueries({ queryKey: ["experiment-list"] });
                  }}
                  className="text-ink-3 hover:text-crimson shrink-0"
                >
                  <Trash2 size={13} />
                </button>
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <Badge tone="neutral">{e.mode}</Badge>
                {e.parent_id && <Badge tone="azure">branch</Badge>}
              </div>
              {e.annotation && <p className="text-xs text-ink-3 mt-1.5 italic">{e.annotation}</p>}
              <p className="text-[10px] text-ink-3 font-mono mt-1.5">{new Date(e.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

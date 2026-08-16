"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listNotebooks, getNotebook, deleteNotebook, notebookExportUrl } from "@/lib/api";
import { Badge } from "@/components/ui/controls";
import { Button } from "@/components/ui/button";
import { X, Trash2, BookOpen, Download, ChevronLeft, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

async function downloadMarkdown(notebookId: string, title: string) {
  const res = await fetch(notebookExportUrl(notebookId, "markdown"));
  const text = await res.text();
  const blob = new Blob([text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/[^a-z0-9]+/gi, "_")}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export function NotebookDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [openNotebookId, setOpenNotebookId] = useState<string | null>(null);

  const { data: notebooks } = useQuery({ queryKey: ["notebook-list"], queryFn: listNotebooks, enabled: open });
  const { data: notebook } = useQuery({
    queryKey: ["notebook", openNotebookId],
    queryFn: () => getNotebook(openNotebookId!),
    enabled: open && !!openNotebookId,
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-panel border-l border-hairline h-full overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display text-lg font-semibold text-ink-1 flex items-center gap-2">
            {openNotebookId && (
              <button onClick={() => setOpenNotebookId(null)} className="text-ink-3 hover:text-ink-1">
                <ChevronLeft size={18} />
              </button>
            )}
            <BookOpen size={16} className="text-teal" /> Notebooks
          </h2>
          <button onClick={onClose} className="text-ink-3 hover:text-ink-1">
            <X size={18} />
          </button>
        </div>

        {!openNotebookId && (
          <div className="space-y-2">
            {notebooks?.length === 0 && (
              <p className="text-xs text-ink-3 font-mono">
                No notebooks yet \u2014 use &quot;Add to Notebook&quot; on any experiment to start one.
              </p>
            )}
            {notebooks?.map((nb) => (
              <div
                key={nb.id}
                className="rounded-lg border border-hairline-2 p-3 cursor-pointer hover:border-hairline transition-colors"
                onClick={() => setOpenNotebookId(nb.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-ink-1 font-medium">{nb.title}</p>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      await deleteNotebook(nb.id);
                      queryClient.invalidateQueries({ queryKey: ["notebook-list"] });
                    }}
                    className="text-ink-3 hover:text-crimson shrink-0"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                {nb.description && <p className="text-xs text-ink-3 mt-1">{nb.description}</p>}
                <p className="text-[10px] text-ink-3 font-mono mt-1.5">
                  {nb.author && `${nb.author} \u00b7 `}updated {new Date(nb.updated_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}

        {openNotebookId && notebook && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="font-display text-base font-semibold text-ink-1">{notebook.metadata.title}</h3>
                {notebook.metadata.description && <p className="text-xs text-ink-3 mt-1">{notebook.metadata.description}</p>}
              </div>
              <Button size="sm" variant="secondary" onClick={() => downloadMarkdown(openNotebookId, notebook.metadata.title)}>
                <Download size={13} /> Export .md
              </Button>
            </div>

            <div className="space-y-3 mt-4">
              {notebook.entries.map((entry, i) => (
                <div key={entry.id} className="rounded-lg border border-hairline-2 p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Badge tone="neutral">{i + 1}. {entry.entry_type}</Badge>
                  </div>
                  {entry.text && <p className="text-xs text-ink-2 leading-relaxed mb-2">{entry.text}</p>}
                  {entry.experiments.map((exp) => (
                    <div key={exp.id} className="rounded-md bg-panel-2 p-2.5 mt-1.5">
                      <div className="flex items-center gap-1.5 mb-1">
                        <ValidationIcon status={exp.health.validation.status} />
                        <p className="text-xs text-ink-1 font-medium">{exp.label}</p>
                      </div>
                      <p className="text-[11px] text-ink-3">
                        {exp.anchor_year} \u2192 {exp.target_year} &middot; peak price {exp.summary.max_price_index as number} &middot;{" "}
                        {exp.cascade_total_affected} nodes affected
                      </p>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ValidationIcon({ status }: { status: string }) {
  if (status === "scored") return <ShieldCheck size={12} className="text-teal shrink-0" />;
  if (status === "not_validated") return <ShieldAlert size={12} className="text-amber shrink-0" />;
  return <ShieldQuestion size={12} className="text-ink-3 shrink-0" />;
}

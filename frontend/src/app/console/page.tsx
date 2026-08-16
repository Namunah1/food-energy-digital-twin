"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createExperiment, getExperiment, branchExperiment, annotateExperiment,
  Experiment, ExperimentCreateBody, listNotebooks, createNotebook, addNotebookEntry,
} from "@/lib/api";
import { Nav } from "@/components/Nav";
import { QueryBar, QueryBarState, defaultQueryState, stateToExperimentBody } from "@/components/console/QueryBar";
import { LivingWorld } from "@/components/console/LivingWorld";
import { ExplanationPanel } from "@/components/console/ExplanationPanel";
import { ExperimentDrawer } from "@/components/console/ExperimentDrawer";
import { NotebookDrawer } from "@/components/console/NotebookDrawer";
import { TimelineReplay } from "@/components/TimelineReplay";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/controls";
import { Badge } from "@/components/ui/controls";
import {
  FlaskConical, GitBranch, Copy, Download, Loader2, MessageSquarePlus, X, BookOpen,
} from "lucide-react";

function ConsoleInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const countryParam = searchParams.get("country");
  const experimentParam = searchParams.get("experiment");

  const [queryState, setQueryState] = useState<QueryBarState>(() =>
    defaultQueryState(countryParam ? { mode: "historical", targetNode: countryParam } : {})
  );
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [selectedCountry, setSelectedCountry] = useState<string | null>(countryParam);
  const [timelineIdx, setTimelineIdx] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [branching, setBranching] = useState(false);
  const [annotating, setAnnotating] = useState(false);
  const [annotationText, setAnnotationText] = useState("");
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareExperiment, setCompareExperiment] = useState<Experiment | null>(null);
  const [compareState, setCompareState] = useState<QueryBarState>(() => defaultQueryState());
  const [notebookDrawerOpen, setNotebookDrawerOpen] = useState(false);
  const [addingToNotebook, setAddingToNotebook] = useState(false);
  const [notebookChoice, setNotebookChoice] = useState<string>("__new__");
  const [newNotebookTitle, setNewNotebookTitle] = useState("");
  const [notebookEntryText, setNotebookEntryText] = useState("");
  const [notebookSaved, setNotebookSaved] = useState(false);

  const { data: notebooksList } = useQuery({ queryKey: ["notebook-list"], queryFn: listNotebooks });

  const runMutation = useMutation({
    mutationFn: (body: ExperimentCreateBody) => createExperiment(body),
    onSuccess: (exp) => {
      setExperiment(exp);
      setBranching(false);
      router.replace(`/console?experiment=${exp.metadata.id}`, { scroll: false });
      queryClient.invalidateQueries({ queryKey: ["experiment-list"] });
    },
  });

  const compareMutation = useMutation({
    mutationFn: (body: ExperimentCreateBody) => createExperiment(body),
    onSuccess: (exp) => {
      setCompareExperiment(exp);
      queryClient.invalidateQueries({ queryKey: ["experiment-list"] });
    },
  });

  const branchMutation = useMutation({
    mutationFn: () => branchExperiment(experiment!.metadata.id, stateToExperimentBody(queryState)),
    onSuccess: (exp) => {
      setExperiment(exp);
      setBranching(false);
      router.replace(`/console?experiment=${exp.metadata.id}`, { scroll: false });
      queryClient.invalidateQueries({ queryKey: ["experiment-list"] });
    },
  });

  // Load an experiment from a deep link (?experiment=id)
  useEffect(() => {
    if (experimentParam && (!experiment || experiment.metadata.id !== experimentParam)) {
      getExperiment(experimentParam).then(setExperiment).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [experimentParam]);

  // Country deep-link: auto-run a historical snapshot for that country
  useEffect(() => {
    if (countryParam && !experiment && !experimentParam) {
      const body = stateToExperimentBody(
        defaultQueryState({ mode: "historical", targetNode: countryParam, anchorYear: 2022, targetYear: 2023 }),
        `${countryParam} \u2014 current state`
      );
      runMutation.mutate(body);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countryParam]);

  useEffect(() => {
    if (experiment) setTimelineIdx(experiment.result.snapshots.length - 1);
  }, [experiment]);

  const run = () => {
    const body = stateToExperimentBody(queryState);
    runMutation.mutate(body);
  };

  const openExperiment = (id: string) => {
    getExperiment(id).then((exp) => {
      setExperiment(exp);
      router.replace(`/console?experiment=${id}`, { scroll: false });
    });
  };

  const exportJson = () => {
    if (!experiment) return;
    const blob = new Blob([JSON.stringify(experiment, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `experiment_${experiment.metadata.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const saveAnnotation = async () => {
    if (!experiment) return;
    const updated = await annotateExperiment(experiment.metadata.id, annotationText);
    setExperiment(updated);
    setAnnotating(false);
  };

  const saveToNotebook = async () => {
    if (!experiment) return;
    let notebookId = notebookChoice;
    if (notebookChoice === "__new__") {
      if (!newNotebookTitle.trim()) return;
      const nb = await createNotebook(newNotebookTitle);
      notebookId = nb.id;
    }
    await addNotebookEntry(notebookId, "experiment", [experiment.metadata.id], notebookEntryText || undefined);
    setNotebookSaved(true);
    setTimeout(() => { setAddingToNotebook(false); setNotebookSaved(false); setNotebookEntryText(""); setNewNotebookTitle(""); }, 1200);
    queryClient.invalidateQueries({ queryKey: ["notebook-list"] });
  };

  const currentSnapshot = experiment?.result.snapshots[Math.min(timelineIdx, experiment.result.snapshots.length - 1)];

  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <main className="mx-auto max-w-[1500px] w-full px-6 py-8 flex-1">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-teal mb-1">Experiment Studio</p>
            <h1 className="font-display text-2xl font-semibold text-ink-1">
              Ask a question about the global food-energy system
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setNotebookDrawerOpen(true)}>
              <BookOpen size={15} /> Notebooks
            </Button>
            <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
              <FlaskConical size={15} /> My Experiments
            </Button>
          </div>
        </div>

        <QueryBar
          value={queryState}
          onChange={setQueryState}
          onRun={branching ? () => branchMutation.mutate() : run}
          running={runMutation.isPending || branchMutation.isPending}
        />

        {!experiment && !runMutation.isPending && (
          <Card className="mt-6 min-h-[300px] flex items-center justify-center">
            <p className="text-ink-3 text-sm font-mono max-w-md text-center">
              Configure a question above and run it. The living world, the explanation, and the
              timeline all populate from one experiment.
            </p>
          </Card>
        )}

        {runMutation.isPending && (
          <div className="mt-6 flex items-center gap-2 text-ink-3 font-mono text-sm">
            <Loader2 size={16} className="animate-spin" /> Running the real ABM\u2026
          </div>
        )}

        {experiment && currentSnapshot && (
          <>
            <div className="flex items-center justify-between mt-6 mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-display text-lg font-semibold text-ink-1">{experiment.metadata.label}</h2>
                <Badge tone="neutral">{experiment.metadata.mode}</Badge>
                {experiment.metadata.parent_id && <Badge tone="azure">branch</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="ghost" onClick={() => { setBranching(true); }}>
                  <GitBranch size={13} /> Branch
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    if (compareExperiment) {
                      // A comparison is already showing — this click clears it
                      // entirely (previously there was no way to exit compare
                      // mode once a comparison experiment had been run).
                      setCompareExperiment(null);
                      setCompareOpen(false);
                    } else {
                      setCompareOpen((v) => !v);
                    }
                  }}
                >
                  <Copy size={13} /> {compareExperiment ? "Exit compare" : "Compare"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setAnnotating(true); setAnnotationText(experiment.metadata.annotation || ""); }}>
                  <MessageSquarePlus size={13} /> Annotate
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setAddingToNotebook(true)}>
                  <BookOpen size={13} /> Add to Notebook
                </Button>
                <Button size="sm" variant="ghost" onClick={exportJson}>
                  <Download size={13} /> Export
                </Button>
              </div>
            </div>

            {branching && (
              <Card className="p-3 mb-4 border-azure/40 flex items-center justify-between">
                <p className="text-xs text-ink-2">
                  Branching from <span className="text-ink-1">{experiment.metadata.label}</span> \u2014 adjust the query bar above and run to create a linked variant.
                </p>
                <button onClick={() => setBranching(false)} className="text-ink-3 hover:text-ink-1"><X size={14} /></button>
              </Card>
            )}

            {annotating && (
              <Card className="p-3 mb-4">
                <div className="flex gap-2">
                  <input
                    value={annotationText}
                    onChange={(e) => setAnnotationText(e.target.value)}
                    placeholder="Add a note about this experiment\u2026"
                    className="flex-1 rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-sm text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
                  />
                  <Button size="sm" onClick={saveAnnotation}>Save</Button>
                  <Button size="sm" variant="ghost" onClick={() => setAnnotating(false)}>Cancel</Button>
                </div>
              </Card>
            )}
            {!annotating && experiment.metadata.annotation && (
              <p className="text-xs text-ink-3 italic mb-4">&ldquo;{experiment.metadata.annotation}&rdquo;</p>
            )}

            {addingToNotebook && (
              <Card className="p-4 mb-4 border-teal/30">
                {notebookSaved ? (
                  <p className="text-sm text-teal">Saved to notebook.</p>
                ) : (
                  <>
                    <p className="text-xs font-mono text-ink-3 uppercase tracking-wider mb-3">Add this experiment to a notebook</p>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <Select value={notebookChoice} onChange={(e) => setNotebookChoice(e.target.value)}>
                        <option value="__new__">+ New notebook</option>
                        {notebooksList?.map((nb) => (
                          <option key={nb.id} value={nb.id}>{nb.title}</option>
                        ))}
                      </Select>
                      {notebookChoice === "__new__" && (
                        <input
                          value={newNotebookTitle}
                          onChange={(e) => setNewNotebookTitle(e.target.value)}
                          placeholder="Notebook title\u2026"
                          className="rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-sm text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
                        />
                      )}
                    </div>
                    <textarea
                      value={notebookEntryText}
                      onChange={(e) => setNotebookEntryText(e.target.value)}
                      placeholder="Conclusion / notes for this entry\u2026"
                      rows={2}
                      className="w-full mt-3 rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-sm text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
                    />
                    <div className="flex gap-2 mt-3">
                      <Button size="sm" onClick={saveToNotebook}>Save entry</Button>
                      <Button size="sm" variant="ghost" onClick={() => setAddingToNotebook(false)}>Cancel</Button>
                    </div>
                  </>
                )}
              </Card>
            )}

            {compareOpen && (
              <Card className="p-4 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-mono text-ink-3 uppercase tracking-wider">Compare against</p>
                  <button onClick={() => setCompareOpen(false)} className="text-ink-3 hover:text-ink-1">
                    <X size={14} />
                  </button>
                </div>
                <QueryBar
                  value={compareState}
                  onChange={setCompareState}
                  onRun={() => compareMutation.mutate(stateToExperimentBody(compareState, "Comparison"))}
                  running={compareMutation.isPending}
                />
              </Card>
            )}

            <div className={compareExperiment ? "grid lg:grid-cols-2 gap-5" : "grid lg:grid-cols-[1fr_380px] gap-5"}>
              <div className="space-y-5">
                <Card className="p-4">
                  <LivingWorld nodes={currentSnapshot.nodes} onSelectCountry={setSelectedCountry} selectedCountry={selectedCountry} />
                </Card>
                <Card className="p-4">
                  <TimelineReplay snapshots={experiment.result.snapshots} timeseries={experiment.result.timeseries} height={320} />
                </Card>
              </div>

              {!compareExperiment && (
                <div className="min-h-[500px]">
                  <ExplanationPanel experiment={experiment} />
                </div>
              )}

              {compareExperiment && (
                <div className="space-y-5">
                  <Card className="p-4">
                    <p className="text-xs font-mono text-ink-3 mb-2">{compareExperiment.metadata.label}</p>
                    <LivingWorld nodes={compareExperiment.result.snapshots[compareExperiment.result.snapshots.length - 1].nodes} />
                  </Card>
                  <ExplanationPanel experiment={compareExperiment} />
                </div>
              )}
            </div>
          </>
        )}
      </main>

      <ExperimentDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onOpenExperiment={openExperiment} currentId={experiment?.metadata.id} />
      <NotebookDrawer open={notebookDrawerOpen} onClose={() => setNotebookDrawerOpen(false)} />
    </div>
  );
}

export default function ConsolePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-abyss" />}>
      <ConsoleInner />
    </Suspense>
  );
}

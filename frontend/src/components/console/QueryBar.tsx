"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fetchShockLibrary } from "@/lib/api";
import type { ExperimentMode, ShockInput, ExperimentCreateBody } from "@/lib/api";
import { Select, Slider, Badge } from "@/components/ui/controls";
import { Button } from "@/components/ui/button";
import { Play, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const MODES: { key: ExperimentMode; label: string; hint: string }[] = [
  { key: "historical", label: "Show me a year", hint: "real calibrated world state" },
  { key: "counterfactual", label: "What if\u2026", hint: "inject a shock into a real year" },
  { key: "projection", label: "Project forward", hint: "future year, with uncertainty" },
];

const KNOWN_EPISODES = [
  { key: "2004_niger", label: "2004-05 Niger/Sahel", year: 2004 },
  { key: "2008", label: "2008 Global Food Crisis", year: 2008 },
  { key: "2011", label: "2010-11 Russia Drought", year: 2011 },
  { key: "2020", label: "2019-20 COVID/Locust", year: 2020 },
  { key: "2022", label: "2022 Ukraine Crisis", year: 2022 },
];

export interface QueryBarState {
  mode: ExperimentMode;
  anchorYear: number;
  targetYear: number;
  knownEpisode: string | null;
  shockType: ShockInput["shock_type"];
  targetNode: string | null;
  severity: number;
  scope: number;
  responses: string[];
  nMc: number;
  evaluatePolicies: boolean;
}

export function defaultQueryState(overrides?: Partial<QueryBarState>): QueryBarState {
  return {
    mode: "counterfactual",
    anchorYear: 2010,
    targetYear: 2020,
    knownEpisode: null,
    shockType: "war",
    targetNode: null,
    severity: 65,
    scope: 30,
    responses: [],
    nMc: 1,
    evaluatePolicies: false,
    ...overrides,
  };
}

export function stateToExperimentBody(s: QueryBarState, label?: string): ExperimentCreateBody {
  const shocks: ShockInput[] =
    s.mode === "historical" && s.knownEpisode
      ? []
      : s.mode === "historical" && !s.knownEpisode
      ? []
      : [{
          shock_type: s.shockType,
          start_step: 1,
          duration: 2,
          severity: s.severity,
          scope: s.scope,
          target_node: s.targetNode,
        }];

  return {
    label,
    mode: s.mode,
    anchor_year: s.anchorYear,
    target_year: s.targetYear,
    known_episode: s.mode === "historical" ? s.knownEpisode : null,
    shocks,
    responses: s.responses,
    n_mc: s.mode === "projection" ? s.nMc : 1,
    explain: true,
    evaluate_policies: s.evaluatePolicies,
    target_country: s.targetNode || undefined,
  };
}

export function QueryBar({
  value,
  onChange,
  onRun,
  running,
}: {
  value: QueryBarState;
  onChange: (s: QueryBarState) => void;
  onRun: () => void;
  running: boolean;
}) {
  const { data: countries } = useQuery({ queryKey: ["qb-countries"], queryFn: api.countries });
  const { data: library } = useQuery({ queryKey: ["qb-shock-library"], queryFn: fetchShockLibrary });
  const [showMore, setShowMore] = useState(false);

  const set = (patch: Partial<QueryBarState>) => onChange({ ...value, ...patch });

  useEffect(() => {
    if (value.mode === "projection" && value.anchorYear > 2024) set({ anchorYear: 2024 });
    if (value.mode !== "projection" && value.targetYear > 2024) set({ targetYear: Math.min(value.targetYear, 2024) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.mode]);

  return (
    <div className="rounded-2xl border border-hairline bg-panel/90 backdrop-blur-sm p-5">
      <div className="flex flex-wrap gap-2 mb-4">
        {MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => set({ mode: m.key, targetYear: m.key === "projection" ? Math.max(2025, value.targetYear) : value.targetYear })}
            className={cn(
              "px-4 py-2 rounded-xl text-sm border transition-colors text-left",
              value.mode === m.key ? "border-teal/60 bg-teal/10 text-teal" : "border-hairline-2 text-ink-2 hover:text-ink-1"
            )}
          >
            <div className="font-medium">{m.label}</div>
            <div className="text-[10px] text-ink-3 font-mono">{m.hint}</div>
          </button>
        ))}
      </div>

      {/* Historical mode */}
      {value.mode === "historical" && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-mono text-ink-3 mb-1.5">Real event (optional)</p>
            <Select
              value={value.knownEpisode ?? ""}
              onChange={(e) => {
                const ep = KNOWN_EPISODES.find((k) => k.key === e.target.value);
                set({ knownEpisode: e.target.value || null, anchorYear: ep ? ep.year - 8 : value.anchorYear, targetYear: ep ? ep.year + 7 : value.targetYear });
              }}
            >
              <option value="">None \u2014 just show the year</option>
              {KNOWN_EPISODES.map((ep) => (
                <option key={ep.key} value={ep.key}>{ep.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <div className="flex justify-between text-xs font-mono text-ink-3 mb-1.5">
              <span>Year</span><span>{value.anchorYear}</span>
            </div>
            <Slider min={2000} max={2024} value={value.anchorYear} onChange={(e) => set({ anchorYear: Number(e.target.value) })} />
          </div>
        </div>
      )}

      {/* Counterfactual mode */}
      {value.mode === "counterfactual" && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-mono text-ink-3 mb-1.5">Event</p>
            <Select value={value.shockType} onChange={(e) => set({ shockType: e.target.value as ShockInput["shock_type"] })}>
              {library && Object.entries(library).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <div className="flex justify-between text-xs font-mono text-ink-3 mb-1.5">
              <span>Year</span><span>{value.anchorYear}</span>
            </div>
            <Slider min={2000} max={2024} value={value.anchorYear} onChange={(e) => set({ anchorYear: Number(e.target.value), targetYear: Number(e.target.value) + 10 })} />
          </div>
          <div>
            <p className="text-xs font-mono text-ink-3 mb-1.5">Target country</p>
            <Select value={value.targetNode ?? ""} onChange={(e) => set({ targetNode: e.target.value || null })}>
              <option value="">Global (by scope)</option>
              {countries?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </div>
          <div>
            <div className="flex justify-between text-xs font-mono text-ink-3 mb-1.5">
              <span>Severity</span><span>{value.severity}</span>
            </div>
            <Slider min={0} max={100} value={value.severity} onChange={(e) => set({ severity: Number(e.target.value) })} />
          </div>
        </div>
      )}

      {/* Projection mode */}
      {value.mode === "projection" && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-xs font-mono text-ink-3 mb-1.5">
              <span>Target year</span><span>{value.targetYear}</span>
            </div>
            <Slider min={2025} max={2060} value={value.targetYear} onChange={(e) => set({ targetYear: Number(e.target.value) })} />
          </div>
          <div>
            <div className="flex justify-between text-xs font-mono text-ink-3 mb-1.5">
              <span>Monte Carlo runs</span><span>{value.nMc}</span>
            </div>
            <Slider min={1} max={20} value={value.nMc} onChange={(e) => set({ nMc: Number(e.target.value) })} />
          </div>
          <div>
            <p className="text-xs font-mono text-ink-3 mb-1.5">Scenario shock (optional)</p>
            <Select value={value.shockType} onChange={(e) => set({ shockType: e.target.value as ShockInput["shock_type"] })}>
              {library && Object.entries(library).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <p className="text-xs font-mono text-ink-3 mb-1.5">Target country</p>
            <Select value={value.targetNode ?? ""} onChange={(e) => set({ targetNode: e.target.value || null })}>
              <option value="">Global (by scope)</option>
              {countries?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </div>
        </div>
      )}

      <button onClick={() => setShowMore((v) => !v)} className="text-xs text-ink-3 hover:text-ink-1 mt-4 font-mono">
        {showMore ? "\u2212 fewer options" : "+ interventions, policy evaluation"}
      </button>

      {showMore && (
        <div className="mt-3 grid sm:grid-cols-2 gap-4 border-t border-hairline pt-4">
          <div>
            <p className="text-xs font-mono text-ink-3 mb-2 uppercase tracking-wider">Response levers</p>
            <div className="space-y-1.5">
              {[
                { key: "reserve_mandate", label: "Strategic reserves" },
                { key: "trade_diversification", label: "Trade diversification" },
                { key: "trader_regulation", label: "Trader regulation + renewables" },
              ].map((r) => (
                <label key={r.key} className="flex items-center gap-2 text-sm text-ink-2">
                  <input
                    type="checkbox"
                    className="accent-teal"
                    checked={value.responses.includes(r.key)}
                    onChange={(e) =>
                      set({ responses: e.target.checked ? [...value.responses, r.key] : value.responses.filter((x) => x !== r.key) })
                    }
                  />
                  {r.label}
                </label>
              ))}
            </div>
          </div>
          <label className="flex items-start gap-2 text-sm text-ink-2">
            <input type="checkbox" className="accent-teal mt-0.5" checked={value.evaluatePolicies} onChange={(e) => set({ evaluatePolicies: e.target.checked })} />
            <span>Also rank real intervention policies against this shock</span>
          </label>
        </div>
      )}

      <div className="flex items-center gap-3 mt-5">
        <Button size="lg" onClick={onRun} disabled={running}>
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {running ? "Running experiment\u2026" : "Run experiment"}
        </Button>
        {value.mode === "projection" && (
          <Badge tone="amber"><Sparkles size={10} className="inline mr-1" />uncertainty reported</Badge>
        )}
      </div>
    </div>
  );
}

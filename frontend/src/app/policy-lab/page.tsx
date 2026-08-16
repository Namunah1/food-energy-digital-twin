"use client";

/**
 * PHASE E (this session): Digital Twin frontend integration for the
 * policy-optimisation work built in Phases A/B/D. Consumes
 * /api/policy_search and /api/policy_search/node_level, which extend
 * (not replace) the pre-existing /api/policy_optimization surface
 * ExplanationPanel.tsx already knows how to render — this page is the
 * missing UI to actually TRIGGER a search, following the same pattern
 * that endpoint's client binding (runPolicyOptimization, lib/api.ts)
 * already established but that no page called (confirmed this session,
 * PHASE4_IMPLEMENTATION_AUDIT.md's original finding: no "policy" named
 * frontend component existed before this phase).
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Nav } from "@/components/Nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, runPolicySearch, runNodeLevelPolicySearch } from "@/lib/api";
import type { PolicySearchCandidate, ShockInput } from "@/lib/api";
import { fmtNumber, cn } from "@/lib/utils";
import { Trophy, Loader2, Sparkles, Target, Info } from "lucide-react";

const NODE_LEVEL_LEVERS = [
  { value: "food_aid", label: "Food aid (donor \u2192 recipient)" },
  { value: "climate_adaptation", label: "Climate adaptation funding" },
  { value: "import_tariff", label: "Import tariff / subsidy" },
  { value: "coordinated_export_restriction", label: "Coordinated export restriction" },
];

const DEFAULT_SHOCK: ShockInput = {
  shock_type: "climate_drought",
  target_node: null,
  start_step: 3,
  duration: 4,
  severity: 0.45,
  scope: 0.3,
};

function CandidateRow({ c, rank }: { c: PolicySearchCandidate; rank: number }) {
  const helped = c.population_saved_millions > 0;
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm",
        rank === 0 ? "bg-teal/10 border border-teal/30" : "bg-panel-2"
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {rank === 0 && <Trophy size={13} className="text-teal shrink-0" />}
        <div className="min-w-0">
          <p className="text-ink-1 truncate font-mono text-xs">{c.label}</p>
          {c.params && Object.keys(c.params).length > 0 && (
            <p className="text-ink-3 text-[11px] truncate">
              {Object.entries(c.params)
                .slice(0, 3)
                .map(([k, v]) => `${k}=${typeof v === "number" ? fmtNumber(v, 2) : v}`)
                .join(", ")}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {c.illustrative_cost != null && (
          <span
            className={cn(
              "font-mono text-[11px]",
              c.within_budget === false ? "text-crimson" : "text-ink-3"
            )}
          >
            cost {fmtNumber(c.illustrative_cost, 1)}
            {c.within_budget === false && " (over budget)"}
          </span>
        )}
        <span
          className={cn(
            "font-mono text-xs font-medium",
            helped ? "text-teal" : "text-crimson"
          )}
        >
          {helped ? "+" : ""}
          {fmtNumber(c.population_saved_millions, 1)}M
        </span>
      </div>
    </div>
  );
}

export default function PolicyLabPage() {
  const { data: countries } = useQuery({
    queryKey: ["policy-lab-countries"],
    queryFn: () => api.countries(),
  });
  const nodeNames = useMemo(() => (countries ?? []).map((c) => c.name).sort(), [countries]);

  const [nRandom, setNRandom] = useState(20);
  const [includeNodeTargeting, setIncludeNodeTargeting] = useState(true);
  const [maxBudget, setMaxBudget] = useState<string>("");

  const generalSearch = useMutation({
    mutationFn: () =>
      runPolicySearch({
        shocks: [DEFAULT_SHOCK],
        start_year: 2022,
        n_steps: 15,
        n_random: nRandom,
        include_fixed_levers: true,
        include_node_targeted_sampling: includeNodeTargeting,
        max_budget: maxBudget ? Number(maxBudget) : undefined,
      }),
  });

  const [nodeLever, setNodeLever] = useState("food_aid");
  const [nodePool, setNodePool] = useState<string[]>([]);
  const nodeSearch = useMutation({
    mutationFn: () =>
      runNodeLevelPolicySearch({
        lever_type: nodeLever,
        node_pool: nodePool.length >= 2 ? nodePool : nodeNames.slice(0, 10),
        shocks: [DEFAULT_SHOCK],
        start_year: 2022,
        n_steps: 15,
        n_random: 20,
      }),
  });

  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <main className="mx-auto max-w-[1400px] w-full px-6 py-10 flex-1">
        <p className="font-mono text-xs uppercase tracking-widest text-teal mb-2">
          Digital Twin — Policy Optimisation
        </p>
        <h1 className="font-display text-3xl font-semibold text-ink-1 mb-1">Policy Lab</h1>
        <p className="text-ink-2 text-sm mb-2 max-w-2xl">
          Searches combinations and intensities of policy levers against a default
          moderate climate+geopolitical shock, ranked by population-at-risk saved
          versus doing nothing.
        </p>
        <div className="flex items-start gap-2 text-ink-3 text-xs mb-8 max-w-2xl bg-panel-2 rounded-lg px-3 py-2">
          <Info size={13} className="mt-0.5 shrink-0" />
          <span>
            Illustrative cost figures (when a budget is set) are not sourced from real
            cost data — see the Digital Twin specification, Section 12. Some
            randomly-sampled candidates may show a <em>negative</em> population-saved
            value: a poorly-targeted policy can make things worse than doing nothing,
            and the search surfaces that rather than hiding it.
          </span>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* General combinatorial search */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Sparkles size={14} className="text-teal" /> General search
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-ink-3 text-xs">
                Samples combinations of global levers (reserve mandates, trade
                diversification, trader regulation, renewable push) plus, optionally,
                node-targeted levers with a randomly-chosen country.
              </p>

              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-xs text-ink-2 flex items-center gap-2">
                  Candidates
                  <input
                    type="number"
                    min={5}
                    max={100}
                    value={nRandom}
                    onChange={(e) => setNRandom(Number(e.target.value))}
                    className="w-16 rounded-lg border border-hairline-2 bg-panel-2 px-2 py-1 text-sm text-ink-1 focus:outline-none focus:ring-1 focus:ring-teal/60"
                  />
                </label>
                <label className="text-xs text-ink-2 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeNodeTargeting}
                    onChange={(e) => setIncludeNodeTargeting(e.target.checked)}
                    className="accent-teal"
                  />
                  Include node-targeted sampling
                </label>
                <label className="text-xs text-ink-2 flex items-center gap-2">
                  Max budget
                  <input
                    type="number"
                    placeholder="none"
                    value={maxBudget}
                    onChange={(e) => setMaxBudget(e.target.value)}
                    className="w-20 rounded-lg border border-hairline-2 bg-panel-2 px-2 py-1 text-sm text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
                  />
                </label>
              </div>

              <Button
                onClick={() => generalSearch.mutate()}
                disabled={generalSearch.isPending}
              >
                {generalSearch.isPending ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Searching…
                  </>
                ) : (
                  "Run search"
                )}
              </Button>

              {generalSearch.isError && (
                <p className="text-crimson text-xs">
                  {(generalSearch.error as Error).message}
                </p>
              )}

              {generalSearch.data && (
                <div className="space-y-1.5 pt-2">
                  <p className="text-ink-3 text-[11px] font-mono mb-2">
                    {generalSearch.data.n_evaluated} candidates evaluated ·
                    objective: {generalSearch.data.objective.split(" (")[0]}
                  </p>
                  {generalSearch.data.ranked_policies.slice(0, 8).map((c, i) => (
                    <CandidateRow key={c.label} c={c} rank={i} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Node-level search */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Target size={14} className="text-teal" /> Node-level search
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-ink-3 text-xs">
                &quot;Which countries should receive this policy?&quot; — searches
                over node targeting for one lever type.
              </p>

              <select
                value={nodeLever}
                onChange={(e) => setNodeLever(e.target.value)}
                className="w-full rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-sm text-ink-1 focus:outline-none focus:ring-1 focus:ring-teal/60"
              >
                {NODE_LEVEL_LEVERS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>

              <div>
                <p className="text-ink-3 text-[11px] mb-1.5">
                  Candidate node pool (defaults to first 10 countries if none selected)
                </p>
                <select
                  multiple
                  value={nodePool}
                  onChange={(e) =>
                    setNodePool(Array.from(e.target.selectedOptions, (o) => o.value))
                  }
                  className="w-full h-28 rounded-lg border border-hairline-2 bg-panel-2 px-2 py-1.5 text-xs text-ink-1 focus:outline-none focus:ring-1 focus:ring-teal/60"
                >
                  {nodeNames.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>

              <Button onClick={() => nodeSearch.mutate()} disabled={nodeSearch.isPending}>
                {nodeSearch.isPending ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Searching…
                  </>
                ) : (
                  "Run node search"
                )}
              </Button>

              {nodeSearch.isError && (
                <p className="text-crimson text-xs">{(nodeSearch.error as Error).message}</p>
              )}

              {nodeSearch.data && (
                <div className="space-y-1.5 pt-2">
                  <p className="text-ink-3 text-[11px] font-mono mb-2">
                    {nodeSearch.data.n_evaluated} node combinations evaluated
                  </p>
                  {nodeSearch.data.ranked_targets.slice(0, 8).map((c, i) => (
                    <CandidateRow key={c.label} c={c} rank={i} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

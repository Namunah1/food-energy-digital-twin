"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { askAdvisor, fetchExperimentHealth } from "@/lib/api";
import type { Experiment } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/controls";
import { Sparkles, ChevronDown, ChevronUp, Send, Loader2, Trophy, HeartPulse, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

export function ExplanationPanel({ experiment }: { experiment: Experiment }) {
  const [openSection, setOpenSection] = useState<string | null>("health");
  const [followUp, setFollowUp] = useState("");
  const [thread, setThread] = useState<{ q: string; a: string }[]>([]);

  const { data: health } = useQuery({
    queryKey: ["experiment-health", experiment.metadata.id],
    queryFn: () => fetchExperimentHealth(experiment.metadata.id),
  });

  const askMutation = useMutation({
    mutationFn: (q: string) => askAdvisor(q),
    onSuccess: (res, q) => setThread((t) => [...t, { q, a: res.answer }]),
  });

  const r = experiment.result;
  const toggle = (s: string) => setOpenSection((cur) => (cur === s ? null : s));

  return (
    <div className="h-full flex flex-col">
      <Card className="p-4 mb-3">
        <div className="flex items-start gap-2.5">
          <Sparkles size={15} className="text-teal shrink-0 mt-0.5" />
          <p className="text-sm text-ink-1 leading-relaxed">{r.explanation}</p>
        </div>
      </Card>

      <div className="space-y-2 overflow-y-auto flex-1">
        {health && (
          <Section
            title="Experiment health"
            open={openSection === "health"}
            onToggle={() => toggle("health")}
          >
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <ValidationIcon status={health.validation.status} />
                <p className="text-xs text-ink-2 leading-relaxed">{health.validation.detail}</p>
              </div>
              <div className="flex items-start gap-2">
                <HeartPulse size={13} className={health.uncertainty.quantified ? "text-teal shrink-0 mt-0.5" : "text-amber shrink-0 mt-0.5"} />
                <p className="text-xs text-ink-2 leading-relaxed">{health.uncertainty.note}</p>
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-ink-3 mb-1.5">Assumptions</p>
                <div className="space-y-1">
                  {health.assumptions.map((a) => (
                    <div key={a.label} className="text-xs">
                      <span className="text-ink-3">{a.label}: </span>
                      <span className="text-ink-2">{a.detail}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-ink-3 mb-1.5">Known limitations</p>
                <ul className="space-y-1 list-disc list-inside">
                  {health.limitations.slice(0, 3).map((l, i) => (
                    <li key={i} className="text-xs text-ink-3 leading-relaxed">{l}</li>
                  ))}
                </ul>
              </div>
              <p className="text-[10px] font-mono text-ink-3">model: {health.model_fingerprint}</p>
            </div>
          </Section>
        )}

        {r.cascade && (
          <Section
            title={`Cascade \u2014 ${r.cascade.total_affected} nodes affected`}
            open={openSection === "cascade"}
            onToggle={() => toggle("cascade")}
          >
            {r.cascade.events.length === 0 && <p className="text-xs text-ink-3">No node crossed the affected threshold.</p>}
            <div className="space-y-1.5">
              {r.cascade.events.slice(0, 10).map((e) => (
                <div key={e.node} className="flex items-center justify-between text-xs">
                  <span className={e.is_origin ? "text-amber" : "text-ink-2"}>
                    step {e.step}: {e.node} {e.is_origin && <Badge tone="amber">origin</Badge>}
                  </span>
                  <span className="font-mono text-crimson">&sigma; \u2212{e.sigma_gap_vs_baseline.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {r.attribution.length > 0 && (
          <Section title="Contribution decomposition" open={openSection === "attribution"} onToggle={() => toggle("attribution")}>
            <div className="space-y-1.5">
              {r.attribution.slice(0, 6).map((a) => (
                <div key={a.node as string} className="text-xs">
                  <div className="flex justify-between text-ink-2 mb-0.5">
                    <span>{a.node as string}</span>
                    <span className="font-mono">{a.food_stress_pct as number}% food stress</span>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {r.uncertainty && (
          <Section title="Uncertainty (Monte Carlo)" open={openSection === "uncertainty"} onToggle={() => toggle("uncertainty")}>
            <div className="space-y-2 text-xs">
              {Object.entries(r.uncertainty).slice(0, 4).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-ink-3 font-mono">{k}</span>
                  <span className="text-ink-1 font-mono">{v.mean} &plusmn; {v.std} (p5-p95: {v.p5}-{v.p95})</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {r.policy_rankings && (
          <Section title="Policy ranking" open={openSection === "policy"} onToggle={() => toggle("policy")}>
            <div className="space-y-2">
              {r.policy_rankings.ranked_policies.slice(0, 3).map((p, i) => (
                <div key={p.lever} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-ink-2">
                    {i === 0 && <Trophy size={11} className="text-teal" />}
                    {p.label}
                  </span>
                  <span className="font-mono text-teal">+{p.population_saved_millions}M saved</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {thread.map((t, i) => (
          <div key={i} className="rounded-lg bg-panel-2 p-3 space-y-1.5">
            <p className="text-xs text-ink-3 font-mono">{t.q}</p>
            <p className="text-xs text-ink-1 leading-relaxed">{t.a}</p>
          </div>
        ))}
        {askMutation.isPending && (
          <div className="flex items-center gap-2 text-ink-3 text-xs font-mono">
            <Loader2 size={12} className="animate-spin" /> thinking\u2026
          </div>
        )}
      </div>

      <div className="flex gap-2 mt-3 pt-3 border-t border-hairline">
        <input
          value={followUp}
          onChange={(e) => setFollowUp(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && followUp.trim()) {
              askMutation.mutate(followUp);
              setFollowUp("");
            }
          }}
          placeholder="Ask a follow-up\u2026"
          className="flex-1 rounded-lg border border-hairline-2 bg-panel-2 px-3 py-2 text-xs text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
        />
        <button
          onClick={() => { if (followUp.trim()) { askMutation.mutate(followUp); setFollowUp(""); } }}
          className="text-teal hover:text-teal/80 px-2"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

function ValidationIcon({ status }: { status: string }) {
  if (status === "scored") return <ShieldCheck size={13} className="text-teal shrink-0" />;
  if (status === "not_validated") return <ShieldAlert size={13} className="text-amber shrink-0" />;
  return <ShieldQuestion size={13} className="text-ink-3 shrink-0" />;
}

function Section({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-hairline">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-mono text-ink-2 hover:text-ink-1">
        {title}
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

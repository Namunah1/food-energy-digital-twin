"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function DashboardPreview() {
  const { data } = useQuery({
    queryKey: ["baseline-metrics-preview"],
    queryFn: () => api.baselineMetrics(8),
  });

  const c = data?.current;

  return (
    <section className="border-t border-hairline">
      <div className="mx-auto max-w-[1400px] px-6 py-20">
        <SectionHeading
          eyebrow="Live"
          title="The dashboard is reading the model right now"
          desc="Every card below is computed live by the ABM's MetricsCollector — not mocked. Open the full dashboard for the complete picture, plus the trade network and country-level breakdowns."
        />
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Global Food Security"
            value={c ? c.GFS.toFixed(2) : "—"}
            tone="teal"
            hint="Population-weighted σ"
          />
          <MetricCard
            label="Population at Risk"
            value={c ? `${(c.PAR_millions / 1000).toFixed(2)}` : "—"}
            unit="bn"
            tone="amber"
            hint="Undernourishment-weighted"
          />
          <MetricCard
            label="Export Ban Rate"
            value={c ? `${(c.EB_export_ban_rate * 100).toFixed(0)}%` : "—"}
            tone="crimson"
            hint="Share of nodes restricting exports"
          />
          <MetricCard
            label="Food Price Index"
            value={c ? c.price_index.toFixed(2) : "—"}
            tone="neutral"
            hint="FAO-anchored (2014-16=1.0)"
          />
        </div>
        <div className="mt-8">
          <Link href="/console">
            <Button variant="secondary">
              Open the Experiment Studio <ArrowRight size={15} />
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  desc,
}: {
  eyebrow: string;
  title: string;
  desc?: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-xs uppercase tracking-widest text-teal mb-3">{eyebrow}</p>
      <h2 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-ink-1">
        {title}
      </h2>
      {desc && <p className="mt-3 text-ink-2 leading-relaxed">{desc}</p>}
    </div>
  );
}

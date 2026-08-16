"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { WorldMapClient } from "@/components/map/WorldMapClient";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ArrowRight, Circle } from "lucide-react";

export function Hero() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["network-preview"],
    queryFn: () => api.network(8),
  });

  return (
    <section className="relative border-b border-hairline">
      <div className="mx-auto max-w-[1400px] px-6 pt-14 pb-10 grid lg:grid-cols-[1.05fr_1fr] gap-10 items-center">
        <div className="animate-fade-up">
          <div className="inline-flex items-center gap-2 rounded-full border border-hairline-2 px-3 py-1 mb-6 text-[11px] font-mono uppercase tracking-widest text-ink-2">
            <Circle size={7} className="fill-teal text-teal" />
            35-node agent-based model · FAO / OWID / ND-GAIN calibrated
          </div>
          <h1 className="font-display text-[2.75rem] leading-[1.05] sm:text-[3.4rem] font-semibold tracking-tight text-ink-1">
            Where does the next
            <br />
            food crisis <span className="text-teal">start</span>,
            <br />
            and where does it <span className="text-amber">spread</span>?
          </h1>
          <p className="mt-6 text-ink-2 text-base sm:text-lg leading-relaxed max-w-xl">
            An interactive decision-support platform built on a systemic-risk
            agent-based model of the global food-energy system —
            grounded in the Gambhir and Homer-Dixon frameworks, retrodicted
            against the 2008 and 2022 crises, and open to any scenario you
            can specify.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/console">
              <Button size="lg">
                Open the Experiment Studio <ArrowRight size={16} />
              </Button>
            </Link>
          </div>
          <div className="mt-10 grid grid-cols-3 gap-6 max-w-md">
            <Stat value="35" label="Modeled nodes" />
            <Stat value="1,190" label="Trade edges" />
            <Stat value="6" label="Named scenarios" />
          </div>
        </div>

        <div className="h-[420px] sm:h-[480px] lg:h-[560px] rounded-2xl border border-hairline overflow-hidden relative">
          {isLoading && (
            <div className="h-full w-full flex items-center justify-center bg-panel text-ink-3 text-sm font-mono">
              Initializing simulation…
            </div>
          )}
          {isError && (
            <div className="h-full w-full flex items-center justify-center bg-panel text-ink-3 text-sm text-center px-6 font-mono">
              Backend unreachable. Start the FastAPI server to see live data.
            </div>
          )}
          {data && <WorldMapClient nodes={data.nodes} edges={data.edges} showEdges />}
          <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg bg-abyss/80 border border-hairline-2 px-3 py-1.5 font-mono text-[11px] text-ink-2">
            node size = population · color = food security (σ)
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-display text-2xl font-semibold text-ink-1 tabular-nums">{value}</div>
      <div className="text-xs text-ink-3 mt-0.5">{label}</div>
    </div>
  );
}

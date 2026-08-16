"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { api } from "@/lib/api";
import { Nav } from "@/components/Nav";
import Link from "next/link";
import { riskColor, riskLabel, fmtNumber } from "@/lib/utils";
import { Search } from "lucide-react";

export default function CountriesPage() {
  const [q, setQ] = useState("");
  const { data: network, isLoading } = useQuery({
    queryKey: ["countries-network"],
    queryFn: () => api.network(10),
  });

  const filtered = useMemo(() => {
    if (!network) return [];
    return network.nodes
      .filter((n) => n.name.toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => a.food_security - b.food_security);
  }, [network, q]);

  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <main className="mx-auto max-w-[1400px] w-full px-6 py-10 flex-1">
        <p className="font-mono text-xs uppercase tracking-widest text-teal mb-2">Digital Twins</p>
        <h1 className="font-display text-3xl font-semibold text-ink-1 mb-1">
          Every node in the model
        </h1>
        <p className="text-ink-2 text-sm mb-6">
          Sorted by food security — most at-risk first. Click any node for its full profile.
        </p>

        <div className="relative max-w-sm mb-6">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search countries or regions…"
            className="w-full rounded-lg border border-hairline-2 bg-panel-2 pl-9 pr-3 py-2 text-sm text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-teal/60"
          />
        </div>

        {isLoading && <p className="text-ink-3 font-mono text-sm">Loading…</p>}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((n) => (
            <Link
              key={n.id}
              href={`/console?country=${encodeURIComponent(n.name)}`}
              className="rounded-xl border border-hairline bg-panel p-4 hover:border-hairline-2 transition-colors flex items-center gap-3"
            >
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ background: riskColor(n.food_security), boxShadow: `0 0 8px ${riskColor(n.food_security)}55` }}
              />
              <div className="min-w-0">
                <p className="font-display font-medium text-ink-1 truncate">{n.name}</p>
                <p className="text-xs text-ink-3 font-mono">
                  σ={n.food_security.toFixed(2)} · {riskLabel(n.food_security)} · {fmtNumber(n.population_millions * 1e6)} pop.
                </p>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}

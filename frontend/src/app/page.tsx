import { Nav } from "@/components/Nav";
import { Hero } from "@/components/landing/Hero";
import { DashboardPreview, SectionHeading } from "@/components/landing/DashboardPreview";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import {
  ArrowRight,
  Sprout,
  Fuel,
  Network,
  ShieldAlert,
  FlaskConical,
  Layers,
  GitBranch,
  FileText,
} from "lucide-react";

const SCENARIOS = [
  {
    code: "S0",
    label: "Baseline",
    desc: "Current trajectory. No shocks, no interventions — shows chronic structural stress in Africa, MENA, and South Asia.",
  },
  {
    code: "S1",
    label: "Climate Cascade",
    desc: "Simultaneous drought in Australia + South Asia and flooding in West Africa. Demonstrates the LFBB (long-fuse/big-bang) mechanism.",
  },
  {
    code: "S2",
    label: "Geopolitical Freeze",
    desc: "Major exporter conflict + broad sanctions, at larger scope than 2022 — the counterfactual for S3/S4.",
  },
  {
    code: "S3",
    label: "Reserve Mandate",
    desc: "S2 triggers, but with FAO-style 3-month strategic reserves pre-positioned. Tests response-before-crisis.",
  },
  {
    code: "S4",
    label: "Trade Diversification",
    desc: "S2 triggers, with pre-existing corridor diversification — a Black Sea Grain Initiative analog.",
  },
  {
    code: "S5",
    label: "Transformational",
    desc: "Reserves + diversification + trader regulation + a 40% renewable push. Systemic restructuring, not incremental response.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />
      <Hero />

      {/* ── Project overview ─────────────────────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20 grid md:grid-cols-3 gap-8">
          <OverviewCard
            icon={<Sprout size={18} />}
            title="Food systems"
            body="35 nodes — 21 hub countries plus 14 regional blocs — each with real FAO production, trade, reserve, and undernourishment data, exchanging food across 1,190 directed trade edges."
          />
          <OverviewCard
            icon={<Fuel size={18} />}
            title="Energy coupling"
            body="Per-country energy-food elasticity (ε_EF) from IEA data drives a bidirectional coupling: energy stress amplifies food prices, and food-price shocks feed back into energy demand."
          />
          <OverviewCard
            icon={<Network size={18} />}
            title="Systemic cascade"
            body="A Stress-Trigger-Crisis engine tracks slow-building food/energy stress per node (LFBB) and propagates discrete shocks through the trade network as ramifying cascades (RC)."
          />
        </div>
      </section>

      {/* ── Research highlights / validation ────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20">
          <SectionHeading
            eyebrow="Validation"
            title="Retrodicted against real crises — reported honestly"
            desc="The model is scored against five real crises using FAO's actual Food Price Index and export-ban / undernourishment figures. Some criteria pass, some don't — the platform surfaces both, because a systemic-risk tool that only shows its wins isn't trustworthy."
          />
          <div className="mt-10 grid lg:grid-cols-2 gap-5">
            <ValidationRow
              year="2008 crisis"
              rows={[
                { k: "Peak FPI error", v: "83.3%", pass: false },
                { k: "Population at risk (order of magnitude)", v: "0.53×", pass: true },
                { k: "Export ban rate direction", v: "captured", pass: false },
              ]}
            />
            <ValidationRow
              year="2022 crisis (Ukraine)"
              rows={[
                { k: "Peak FPI error", v: "9.0%", pass: true },
                { k: "Population at risk (order of magnitude)", v: "0.50×", pass: true },
                { k: "Export ban rate", v: "0.457 vs real 0.20", pass: true },
              ]}
            />
          </div>
          <div className="mt-5 rounded-xl border border-hairline bg-panel p-5 flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-ink-2 max-w-xl">
              Three more episodes are wired into the model: <span className="text-ink-1">2010-11 Russia drought</span> and{" "}
              <span className="text-ink-1">2019-20 COVID / East Africa locust</span> (both scored the same way as
              2008/2022), plus <span className="text-ink-1">2004-05 Niger/Sahel</span> — a regional crisis reported
              descriptively rather than forced against a global-FPI benchmark it was never meant to match. Numbers
              shift slightly run to run (Monte Carlo) — see them live rather than a snapshot here.
            </p>
            <Link href="/console">
              <Button variant="secondary">
                Explore in the Studio <ArrowRight size={15} />
              </Button>
            </Link>
          </div>
          <p className="mt-6 text-sm text-ink-3 max-w-2xl">
            Full criteria, methodology, and the coping-capacity calibration
            (LightGBM, validation R²=0.86) are in the published methods paper
            — see Publications below.
          </p>
        </div>
      </section>

      {/* ── Scientific contributions ─────────────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20">
          <SectionHeading
            eyebrow="Framework"
            title="Two frameworks, one engine"
            desc="The Stress-Trigger-Crisis engine operationalizes Homer-Dixon's slow-scarcity model and Gambhir's systemic-risk architecture as a running simulation, not just a diagram."
          />
          <div className="mt-10 grid md:grid-cols-3 gap-5">
            <ContribCard
              icon={<ShieldAlert size={18} />}
              title="LFBB — Long Fuse, Big Bang"
              body="Per-node food/energy stress accumulates silently for years. A node only visibly overloads (FS_index / CC_index > 1.0) once its coping capacity is exceeded — by which point the crisis is already structural."
            />
            <ContribCard
              icon={<Network size={18} />}
              title="RC — Ramifying Cascade"
              body="Overloaded nodes raise contagion probability on adjacent trade edges for a fixed window, amplifying export-ban clustering and price feedback across the network — the mechanism behind 2008 and 2022."
            />
            <ContribCard
              icon={<Layers size={18} />}
              title="4 SAV indices"
              body="Scale, Homogeneity, Connectivity, and Power — Gambhir's System Architecture Vulnerability indices — are recomputed every step from live trade and capital concentration, not fixed assumptions."
            />
          </div>
        </div>
      </section>

      {/* ── Scenario explorer preview ───────────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <SectionHeading
              eyebrow="Scenario Lab"
              title="Six named futures, or build your own"
              desc="Each research scenario ships with a full storyline and an explicit response-trade-off writeup. The Scenario Lab lets you compose your own shocks and interventions on top of the same engine."
            />
            <Link href="/console">
              <Button variant="secondary">
                Open the Experiment Studio <ArrowRight size={15} />
              </Button>
            </Link>
          </div>
          <div className="mt-10 grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {SCENARIOS.map((s) => (
              <div
                key={s.code}
                className="rounded-xl border border-hairline bg-panel p-5 hover:border-hairline-2 transition-colors"
              >
                <Badge tone={s.code === "S0" ? "neutral" : s.code === "S5" ? "teal" : "amber"}>
                  {s.code}
                </Badge>
                <h3 className="font-display font-semibold mt-3 text-ink-1">{s.label}</h3>
                <p className="mt-2 text-sm text-ink-2 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <DashboardPreview />

      {/* ── Architecture overview ───────────────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20">
          <SectionHeading
            eyebrow="Under the hood"
            title="The frontend never computes science"
            desc="Every number on this platform is produced by the Python ABM and served over REST/WebSocket. The browser only requests, renders, and lets you explore."
          />
          <div className="mt-10 grid md:grid-cols-4 gap-px bg-hairline rounded-xl overflow-hidden border border-hairline">
            <ArchLayer
              title="UI"
              items={["Next.js 15 / TypeScript", "Tailwind, Recharts, Leaflet", "React Query"]}
            />
            <ArchLayer
              title="API"
              items={["FastAPI", "REST + WebSocket", "Pydantic validation"]}
            />
            <ArchLayer
              title="Simulation"
              items={["FoodEnergyModel (Mesa)", "STC engine", "Scenario registry — unmodified"]}
            />
            <ArchLayer
              title="Data"
              items={["FAO / OWID / ND-GAIN", "35-node trade network", "node_panel 2000–2023"]}
            />
          </div>
        </div>
      </section>

      {/* ── Publications ────────────────────────────────────────────── */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-[1400px] px-6 py-20">
          <SectionHeading eyebrow="Read the research" title="Publications & methods" />
          <div className="mt-10 grid md:grid-cols-2 gap-5">
            <PubCard
              icon={<FileText size={18} />}
              title="Systemic Risk Assessment Report"
              body="Full methods, calibration, sensitivity analysis (Sobol + OAT, 96+112 runs), and retrodiction scoring against 2008/2022."
            />
            <PubCard
              icon={<FlaskConical size={18} />}
              title="Journal manuscript"
              body="Formal write-up of the STC engine, the Gambhir SAV indices, and the ML-calibrated coping-capacity model (LightGBM, val R²=0.86)."
            />
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="mt-auto">
        <div className="mx-auto max-w-[1400px] px-6 py-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div>
            <p className="font-display font-semibold text-ink-1">Systemic Risk Observatory</p>
            <p className="text-sm text-ink-3 mt-1">
              Built on the Gambhir (2025) + Homer-Dixon (2015) frameworks. Not a forecast — a decision-support instrument.
            </p>
          </div>
          <div className="flex items-center gap-4 text-ink-3">
            <GitBranch size={18} />
            <span className="text-xs font-mono">v1.0.0 · scientific core unmodified</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function OverviewCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div>
      <div className="w-9 h-9 rounded-lg bg-panel-2 border border-hairline-2 flex items-center justify-center text-teal">
        {icon}
      </div>
      <h3 className="font-display font-semibold mt-4 text-ink-1">{title}</h3>
      <p className="mt-2 text-sm text-ink-2 leading-relaxed">{body}</p>
    </div>
  );
}

function ContribCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-xl border border-hairline bg-panel p-5">
      <div className="w-9 h-9 rounded-lg bg-panel-2 border border-hairline-2 flex items-center justify-center text-amber">
        {icon}
      </div>
      <h3 className="font-display font-semibold mt-4 text-ink-1">{title}</h3>
      <p className="mt-2 text-sm text-ink-2 leading-relaxed">{body}</p>
    </div>
  );
}

function PubCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-xl border border-hairline bg-panel p-5 flex gap-4">
      <div className="w-9 h-9 shrink-0 rounded-lg bg-panel-2 border border-hairline-2 flex items-center justify-center text-azure">
        {icon}
      </div>
      <div>
        <h3 className="font-display font-semibold text-ink-1">{title}</h3>
        <p className="mt-1.5 text-sm text-ink-2 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

function ArchLayer({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="bg-panel p-5">
      <p className="font-mono text-[11px] uppercase tracking-widest text-teal">{title}</p>
      <ul className="mt-3 space-y-2">
        {items.map((it) => (
          <li key={it} className="text-sm text-ink-2">
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ValidationRow({
  year,
  rows,
}: {
  year: string;
  rows: { k: string; v: string; pass: boolean }[];
}) {
  return (
    <div className="rounded-xl border border-hairline bg-panel p-5">
      <h3 className="font-display font-semibold text-ink-1">{year}</h3>
      <div className="mt-4 space-y-3">
        {rows.map((r) => (
          <div key={r.k} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-ink-2">{r.k}</span>
            <span
              className={`font-mono ${r.pass ? "text-teal" : "text-crimson"}`}
            >
              {r.v}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

# Scientific Design Specification
## Global Food-System Digital Twin — Canonical Blueprint

**Purpose of this document:** a single, self-contained specification from
which an independent research group could implement the entire platform,
without needing to read the session-by-session investigation history that
produced it. Every equation, constant, and architectural decision below is
either (a) already implemented and verified in the current codebase, or
(b) explicitly marked **[PROPOSED — NOT YET IMPLEMENTED]**. Nothing in
this document should be read as a validation claim — see Section 13 for
the model's actual, current validation status, which is mixed and stated
honestly.

---

## 1. Mathematical architecture — overview

The simulator is a discrete-time (annual-step), 35-node agent-based model
coupled through a directed trade network. Each node `i` carries a state
vector updated each tick `t → t+1` by five coupled subsystems, in this
fixed order (the order is causally load-bearing — see Section 2):

```
energy stress → agent production/consumption/export-policy (pre-trade)
  → trade resolution → post-trade food-security recompute
  → STC stress accumulation / overload detection / trigger injection
  → global price update → metrics
```

This ordering was the subject of a dedicated investigation this session
(the "Phase 2.5" sequencing fix) and is not arbitrary: evaluating overload
before trade resolves structurally misrepresents import-dependent nodes'
food security, and this document's baseline assumes the corrected order.

---

## 2. Causal graph

Full subsystem-by-subsystem decomposition (inputs, outputs, equations,
feedbacks, saturation, hidden coupling) exists in
`PHASE2_5B_CAUSAL_DECOMPOSITION.md` and is incorporated here by reference
for the ten subsystems it covers (RC price amplification, trade, STC
overload accumulation, food security, coping capacity, export-ban
cascades, energy-food coupling, reserve dynamics, climate stress,
political instability). The single load-bearing finding from that
document, restated here because every other section depends on it:

**The dominant loop:** `overload count → RC price shock → global price →
every node's FS_index (via price_ratio) → overload count`. This loop
currently has **no intrinsic negative feedback** — everything that
constrains it is borrowed from the price system's hard clamp
(`PRICE_CEILING=5.00`) and mean-reversion term, not from the amplification
mechanism itself. **This is the single highest-priority open item in the
entire specification** (Section 20) and blocks the optimisation layer
(Section 10) from producing trustworthy policy rankings until resolved.

Two mechanisms are confirmed **dead code** as of this session and should
either be wired up or removed before independent re-implementation, so a
new team does not spend effort re-implementing something inert:
`STCEngine`'s `_rc_contagion_boost`/`_cascade_active` (computed, never
read anywhere) and `trade.py`'s `G_BASE` gravity constant (declared,
never used — the actual gravity volume comes from real per-edge `C_ij`
capacity data, not a global gravity constant).

---

## 3. All state variables

| Variable | Symbol | Type | Update rule | Bounds |
|---|---|---|---|---|
| Population | P_i(t) | endogenous | §9 (below) | ≥ 1 |
| Capital | K_i(t) | endogenous | §10 | ≥ 0.1 |
| Technology | T_i(t) | endogenous | §10, capped logistic | [T_i(0), 1.10×T_i(0)] |
| Food stocks (imperish/perish/animal) | F_i(t) | endogenous | production/consumption | ≥ 0, imperishable capped at `MAX_STOCK_YEARS×D_i` |
| Strategic reserves | R_i(t) | endogenous | §8 | ≥ 0 |
| Food security ratio | σ_i(t) | endogenous (memoryless ratio) | §4 | not clipped |
| FS_index | — | endogenous, accumulates | §3 | [0, 2] |
| CC_index | — | endogenous, memoryless | §5 | [0.05, 1.0] |
| Energy stress index | ES_i(t) | endogenous | §7 | [0, 1] |
| Biofuel land share | ξ_i(t) | endogenous, rate-limited | §7 Arrow 2 | [0, 0.15] |
| Export fraction | — | endogenous, policy-overridable | §6/§11 | [0, μ_i] |
| Global price | p(t) | endogenous, single scalar shared by all nodes | Section 6 below | [0.80, 5.00] |
| **[PROPOSED]** Soil quality | Q_soil,i(t) | endogenous | new | [0, 1] |
| **[PROPOSED]** Fertilizer stocks (N,P,K) | Φ_i(t) | endogenous | new | ≥ 0 |
| **[PROPOSED]** Water reservoir stock | W_stock,i(t) | endogenous | new | ≥ 0 |

---

## 4. All policy variables

(Full lever-by-lever specification, including exact equations and which
existing hook each routes through, is in
`PHASE3_DIGITAL_TWIN_ARCHITECTURE.md` Parts A3/B; summarised here.)

| Lever | Level | Status |
|---|---|---|
| Export fraction cap | Node | **Implemented** (`agent.export_fraction`) |
| Sanction / trade-risk penalty | Edge | **Implemented, unused by default** (`sanction_penalty`) |
| Reserve target / release | Node | Implemented mechanically; target formula needs redefinition (Section 20) |
| Import tariff/subsidy | Node | **[PROPOSED]** — affordability multiplier |
| Fertilizer allocation | Node | **[PROPOSED]** — requires Section 3's Φ_i state |
| Climate adaptation investment | Node | **[PROPOSED]** — modifies climate-modifier coefficients |
| Food aid transfer | Node-pair | **[PROPOSED]** — bypasses trade affordability gate |
| FAO strategic reserve pool | Global | **[PROPOSED]** — new `R_global(t)` |
| Emergency reserve release | Global | **[PROPOSED]** — rule on top of `R_global(t)` |
| Energy release/subsidy | Node | **Implemented** — reuse of `apply_energy_shock` in reverse |
| Shipping corridor protection | Edge | **[PROPOSED]** — targets existing but unexposed `logistics_disruption` |

---

## 5. Global variables

| Variable | Scope | Status |
|---|---|---|
| Global price p(t) | Single shared scalar across all 35 nodes | Implemented — see Section 20 for the known limitation this creates |
| EROI penalty (global) | Shared accumulator, monotonic non-decreasing | Implemented (`EnergyModule._eroi_penalty_global`) |
| RC cascade window state | `_cascade_active_until` | Implemented but its downstream consumer is dead code (Section 2) |
| **[PROPOSED]** R_global(t) — FAO strategic reserve pool | New | Section 4 |
| **[PROPOSED]** Global fertilizer/shipping indices | New exogenous drivers | Part A2, architecture doc |

---

## 6. Climate variables

| Variable | Current status | Equation |
|---|---|---|
| drought_index, heatwave_index, flood_index | Implemented, trigger-injected only (not yet continuous) | feed `climate_modifier` |
| climate_modifier (C_i) | Implemented | `C_i = max(0.05, 1 − 0.40×drought − 0.35×heatwave − 0.25×flood)` |
| **[PROPOSED]** Rainfall anomaly (continuous) | Not implemented | `drought_index_i(t) = clip((rainfall_climatology_i − rainfall_i(t))/rainfall_climatology_i, 0, 1)` |
| **[PROPOSED]** Temperature anomaly → heat stress | Not implemented | `heat_stress_i(t) = clip((temp_anomaly_i(t) − heat_threshold)/heat_range, 0, 1)` |

**Known structural issue, must be resolved before C1 is added (see
architecture doc Part C1):** `climate_modifier` currently feeds production,
FS_index, and ES_index simultaneously (triple-counting) — introducing a
continuous rainfall driver without addressing this will triple the
effective weight of every rainfall anomaly relative to the discrete
triggers currently calibrated against real 2008/2022 episodes.

---

## 7. Resource variables

| Resource | Symbol | Status |
|---|---|---|
| Arable land | L_i | Implemented, static |
| Water (production input) | W_i | Implemented, static Cobb-Douglas input |
| Energy (fossil/renewable/electric) | E_fuel,i, E_renew,i, E_elec,i | Implemented, dynamic |
| **[PROPOSED]** Fertilizer N/P/K | Φ_i = (N_i, P_i, K_i) | Not implemented — currently only a static, one-time T_i calibration input, not a live tradeable/depletable stock |
| **[PROPOSED]** Water reservoir/aquifer stock | W_stock,i | Not implemented — no distinction between renewable rainfall-fed water and depletable groundwater |

---

## 8. Trade variables

Fully implemented, real 35×35 directed network from `network_weights.csv`:

- `C_ij` — edge capacity (kcal/year proxy), with an optional
  `C_ij_corrected` Agricultural Trade Multiplier correction for
  agricultural-exporter underweighting (documented, partial — full
  correction blocked pending FAO Detailed Trade Matrix access).
- `κ_ij` — transaction cost ∈ [0,1].
- `ρ_ij` — political/sanction risk ∈ [0.05, 0.95], effective risk
  `ρ_ij_eff = clip(ρ_ij + sanction_penalty, 0.05, 0.95)`.
- Trade volume: `volume = min(export_avail, cap_volume, buyer_deficit×1.2,
  affordable_kcal)`, `affordable_kcal = (K_buyer / p^1.2) × 10^12`.
- **Single shared global price** for affordability across every edge — a
  known simplification (Section 20).

---

## 9. Geopolitical variables

| Variable | Status |
|---|---|
| Political risk ρ_i (node-level, feeds CC_index) | Implemented, **static** — never updated by simulation dynamics |
| Political risk ρ_ij (edge-level, feeds trade risk gate) | Implemented, static baseline + dynamic `sanction_penalty` overlay |
| Export bans / contagion | Implemented (`_propagate_export_ban`), probabilistic, self-limiting (one-tick persistence unless independently justified by the node's own σ) |

**Explicit design finding (Phase 2.5b):** there is no feedback from the
simulation's own trajectory (e.g. a famine) back into rising political
risk — this is a deliberate scope boundary, not an oversight, and should
remain a boundary unless a future session explicitly designs that specific
new feedback loop.

---

## 10. Optimisation objective

**[PROPOSED — not yet implemented, full formulation in
`PHASE3_DIGITAL_TWIN_ARCHITECTURE.md` Part G]**

- **State space:** full Section 3 vector × 35 nodes + Section 5 globals.
- **Action space:** Section 4's controllable levers, bounded.
- **Objective (minimise):** population-at-risk (PAR), already computed by
  `metrics.py` and already the strongest-performing metric in the current
  retrodiction battery (passed 3 of 4 scored historical episodes even
  under the model's currently-imperfect FPI fit) — chosen deliberately
  over the FPI metric, which Section 2 shows is directly downstream of the
  unresolved RC-amplification loop and would bias optimisation results
  toward whatever happens to avoid that loop's activation threshold rather
  than genuine policy merit.
- **Constraints:** policy budget bounds — **currently uncosted**; no
  USD-per-unit cost exists yet for reserve levy, aid volume, or adaptation
  funding. This must be sourced (FAO/World Bank cost-of-storage
  literature is the proposed starting point) before a cost-constrained
  search is meaningful.
- **Search method:** black-box / derivative-free (Bayesian optimisation or
  evolutionary strategy) over the action space — justified by the model's
  demonstrated per-replica runtime (~1 second, confirmed this session across
  hundreds of real runs), which makes a non-differentiable, sample-based
  search tractable without requiring a differentiable surrogate.
- **Explainability:** reuse the existing `crisis_attribution()` function
  (real, already implemented, already used throughout this session's
  Phase 2 catalogue) to decompose *why* a candidate policy's outcome
  occurred, per node — no new explainability mechanism should be built.

---

## 11. Constraints

| Constraint class | Status |
|---|---|
| Physical (stock non-negativity, capacity caps) | Implemented throughout (Section 3's bounds column) |
| Policy budget (cost of reserves, aid, adaptation) | **Not implemented, not costed** — flagged above |
| Trade network structural limits (`C_ij`) | Implemented |
| Political feasibility (e.g. a node refusing a policy) | **Not modelled** — out of current scope, flagged for a future session if wanted |

---

## 12. Calibration sources

Full source-to-variable mapping for every currently-implemented variable
is in `docs/DATA_PROVENANCE.md` (OWID energy/CO2 data, World Bank
indicators, FAO FPI/Food Balance Sheets/Crop Production, ND-GAIN climate
vulnerability). The one subsystem with genuine, cross-validated empirical
calibration is CC_index (ML regression against FAO undernourishment,
cross-validated R²=0.86, Phase 3 session finding) — this is the reference
standard new calibration work should be held to.

**New data sources required for Section 6/7 [PROPOSED] variables** (none
currently in `data/raw/`):

| New driver | Proposed source | Confidence tier |
|---|---|---|
| Rainfall anomaly | CHIRPS (UCSB Climate Hazards Group) | High |
| Temperature anomaly | Berkeley Earth / NOAA GHCN | High |
| Fertilizer N/P/K trade flows | IFA (International Fertilizer Association), World Bank `AG.CON.FERT.ZS` extended to full time series | High |
| Fertilizer production-response curve | Agronomic literature (Mitscherlich-type) | Medium |
| Water withdrawal by sector | FAO AQUASTAT | Medium |
| Groundwater depletion | GRACE satellite gravimetry | Low (coarse spatial resolution) |
| Soil quality/degradation | FAO Global Soil Organic Carbon map / ISRIC SoilGrids | Low (sparse national time series) |
| Climate adaptation effectiveness | **No source identified** | Low — explicitly do not force an ML fit here without an independent validation target (Section 13) |

---

## 13. Validation strategy

**Current, real status (not aspirational):** the retrodiction battery
scores 4 historical episodes (2008, 2010-11, 2019-20, 2022) against real
FAO FPI, export-ban-rate, and PAR figures. As of the most recent verified
run (post Phase 2.5 sequencing fix, this session): POM score 0.300 (target
≥0.70), PAR passes 3/4 episodes, export-ban-rate passes 3/4, peak-FPI
currently fails all 4 (the RC-amplification issue, Section 2). This is
stated plainly because a document claiming otherwise would not survive an
independent group re-running the code — which already happened once this
session, when a previously-reported "9.1% error / PASS" 2022 result turned
out to be a measurement artefact.

**Validation strategy for [PROPOSED] additions:**
1. Any new driver must pass the same retrodiction discipline before being
   trusted: hold out a real historical episode, compare model output to
   real observed values, report the error honestly (see the pattern
   already established in `retrodiction.py`).
2. New composite indices (e.g. a fertilizer-response function) should
   follow the CC_index precedent — cross-validated regression against an
   independent real target, not a hand-set constant, wherever a target
   series genuinely exists (Section 12's confidence tiers).
3. **Before the optimisation layer (Section 10) is trusted for real policy
   recommendations, the RC-amplification negative-feedback gap (Section 2)
   must be resolved and the full retrodiction battery re-run to confirm
   the fix doesn't reintroduce the long-horizon degradation found earlier
   this session when the trade-sequencing fix was merged.**

---

## 14. Data sources

Consolidated list (full field-level mapping in `docs/DATA_PROVENANCE.md`):
OWID Energy/CO2 data, World Bank (arable land, water stress, trade % GDP,
life expectancy, fertilizer kg/ha, UHC index), FAO (Food Price Index, Food
Balance Sheets, Crop Production), ND-GAIN (climate vulnerability). New
sources required for the proposed environmental expansion are listed in
Section 12.

---

## 15. Integration plan

Phased, in dependency order — **do not implement out of this order**,
since later phases assume earlier ones are resolved:

1. **Resolve the RC-amplification negative feedback** (Section 2) — this
   is a correction to an *existing* subsystem, not new scope, and every
   subsequent phase's validity depends on it.
2. **Re-run the full retrodiction battery** after (1), confirm no
   long-horizon regression (repeat of this session's Phase 2.5 merge
   discipline).
3. **Add the one genuinely new production term** (labour availability,
   Section 20) needed for pandemic representation — smallest new-state
   addition, well-precedented functional form.
4. **Wire up Section 6/7's [PROPOSED] environmental drivers**, resolving
   the triple-counting issue as part of the same change, not after.
5. **Implement Section 4's policy levers**, in order of implementation
   cost: energy release/subsidy (reuses existing shock interface) →
   export restriction coordination (reuses existing 3-regime logic) →
   sanctions (reuses existing `sanction_penalty` hook) → aid/fertilizer
   redistribution (genuinely new transfer pathway) → reserve pool (new
   global state) → adaptation funding (weakest calibration, lowest
   priority).
6. **Build the optimisation loop** (Section 10) only after (1)-(5).
7. **Software/deployment work** (Sections 17-19 below) can proceed in
   parallel with (3)-(5), since it does not depend on the scientific
   corrections in (1)-(2) — but must not be used for real policy search
   results until (6) is gated by (1)-(2).

---

## 16. Mathematical equations — consolidated reference

(Full derivations and constants in `docs/EQUATIONS.md` and
`PHASE2_5B_CAUSAL_DECOMPOSITION.md`; core equations restated here for a
self-contained reference.)

**Production (Cobb-Douglas):**
`Q_i = P_i × c_i × A_i × (L_food,i/L_REF)^0.30 × W_i^0.25 × (E_fuel,i/E_REF)^0.20 × T_i^0.25 × C_i × r_renew`

**Food security:**
`σ_i(t) = (Q_i + R_draw,i + stock_bonus,i) / D_i`, `R_draw,i = min(R_i, 0.30×D_i)`, `stock_bonus,i = min(max(0, F_imperish,i − θ_imperish×D_i), 0.50×D_i)`

**Export policy (3-regime):**
`σ_i ≤ 1.0 → export_fraction=0`; `1.0 < σ_i ≤ σ_safe,i → export_fraction = 0.60×((σ_i−1)/(σ_safe,i−1))^1.5`; `σ_i > σ_safe,i → export_fraction = min(μ_i, 0.90)`

**FS_index accumulation:**
`FS_i(t) = clip(FS_i(t−1) + 0.05×max(0,1−σ_i) − 0.03×max(0,σ_i−σ_safe,i) + 0.20×ES_i + 0.15×(1−C_i), 0, 2)` *(rate constants per `stc_engine.py`; exact values should be re-confirmed against source before independent re-implementation, not assumed from this summary)*

**CC_index:**
`CC_i = clip(0.4749×min(1,T_i/2) + 0.3002×min(1,K_i/1000) − 0.1066×ρ_i + 0.0031×min(1,R_i/(0.15×D_i)) − 0.1152×climate_vuln_i, 0.05, 1.0)` *(ML-calibrated weights, Phase 3 cross-validated regression)*

**Global price:**
`p(t+1) = clip(p(t)×exp(1.5×0.08×(D_tot−Q_tot)/D_tot) + 0.04×(p_adaptive−p(t)) + 0.45×ES_global×p(t), 0.80, 5.00)`

**RC price amplification:** fires when `n_overloaded(t) > n_overloaded(t−1)`; `p ← clip(p × (1 + 0.021×n_overloaded), 0.80, 5.00)`.

**Trade volume:** `volume_ij = min(export_fraction_i×F_imperish,i, C_ij×(1−κ_ij)×(1−logistics_factor), 1.2×buyer_deficit_j, (K_j/p^1.2)×10^12)`

**Energy stress:** `ES_i = clip(step×0.018×fossil_share_i×0.40 + EROI_global×fossil_share_i + 0.25×ρ_i×(1−self_suff_i) + 0.10×(1−C_i) − renew_offset_i, 0, 1)`

---

## 17. Software architecture

**Current, real architecture** (verified this session against the live
codebase, not assumed):

- **Simulation core:** Python, Mesa 3.x-based ABM (`model.py`, `agent.py`,
  `trade.py`, `stc_engine.py`, `energy.py`, `political_economy.py`,
  `prices.py`, `scenarios.py`, `retrodiction.py`) — vendored, unmodified
  scientific logic; `model_bridge.py` in the backend calls it directly and
  explicitly does not reimplement any scientific quantity.
- **Backend:** FastAPI (`main.py`), currently ~30 REST endpoints (Section
  19), synchronous per-request computation with `functools`-level caching
  — no job queue yet.
- **Frontend:** Next.js/React.
- **Persistence:** SQLite (`experiment_store.py`, `notebook_store.py`),
  single-table JSON-document pattern (Section 18) — real durable storage,
  explicitly documented in its own module docstring as not
  production-multi-user-grade.
- **Deployment:** currently `docker-compose`, two containers, no
  Kubernetes.

**Recommended target architecture** (per this session's Phase 5 deployment
analysis, `PHASE5_DEPLOYMENT_ARCHITECTURE.md`, carried forward
unchanged): simulation-worker pods replicated at the whole-simulation
level (not per-country microservices — the trade-clearing step is a
synchronous fixed-point calculation, decomposing it into 35 pods would add
network round-trip latency for zero benefit), a job queue (NATS
JetStream) decoupling request acceptance from computation, KEDA
queue-depth autoscaling, and Postgres replacing SQLite for the experiment
store — this last item is a **correctness fix**, not a scaling nicety:
SQLite's single-writer model does not survive multi-replica deployment.

---

## 18. Database schema

**Current schema** (`experiment_store.py`, verified from source):
```sql
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    mode TEXT NOT NULL,
    parent_id TEXT,
    created_at TEXT NOT NULL,
    annotation TEXT,
    payload TEXT NOT NULL   -- full Experiment dict, JSON-serialised
);
CREATE INDEX idx_parent ON experiments(parent_id);
```
A single-table, document-store pattern — simple, but everything beyond
`id`/`label`/`mode`/`parent_id`/`created_at` is opaque JSON, unqueryable
without deserialising every row. Adequate for the current single-user,
single-process deployment; not adequate for the Digital Twin's needs.

**[PROPOSED] normalised schema for the Digital Twin**, extending rather
than discarding the existing pattern (the `payload` JSON column is kept
for full-fidelity round-tripping; new columns/tables make the
policy-relevant fields queryable):

```sql
-- Existing table, extended
ALTER TABLE experiments ADD COLUMN scenario_type TEXT;      -- historical|counterfactual|policy_search
ALTER TABLE experiments ADD COLUMN pom_score REAL;
ALTER TABLE experiments ADD COLUMN par_millions REAL;

-- New: per-node time series, queryable without JSON deserialisation
CREATE TABLE node_timeseries (
    experiment_id TEXT REFERENCES experiments(id),
    node TEXT NOT NULL,
    step INTEGER NOT NULL,
    sigma REAL, fs_index REAL, cc_index REAL, es_index REAL,
    overload_food BOOLEAN, price_index REAL,
    PRIMARY KEY (experiment_id, node, step)
);

-- New: policy runs (Section 10's action space, one row per search evaluation)
CREATE TABLE policy_runs (
    id TEXT PRIMARY KEY,
    parent_search_id TEXT,
    action_vector TEXT NOT NULL,     -- JSON: {lever: value, ...}
    objective_value REAL NOT NULL,   -- PAR, per Section 10
    experiment_id TEXT REFERENCES experiments(id),
    created_at TEXT NOT NULL
);

-- New: calibration provenance (Section 12/13 traceability)
CREATE TABLE calibration_sources (
    variable_name TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,          -- matches docs/DATA_PROVENANCE.md IDs
    confidence_tier TEXT NOT NULL,    -- high|medium|low, per Section 12
    last_validated TEXT
);
```

---

## 19. API contracts

**Current, real endpoints** (verified against `main.py`, not invented):
`GET /api/health`, `/api/countries`, `/api/scenarios`,
`/api/baseline/metrics`, `/api/baseline/nodes`, `/api/network`,
`/api/country/{name}`, `/api/country/{name}/history`,
`POST /api/research_scenario`, `GET /api/historical/episodes`,
`/api/historical/{key}`, `POST /api/run_simulation`, `POST /api/compare`,
`GET /api/network/centrality`, `/api/time_machine`, `/api/real_year/{year}`,
`GET /api/advisor/providers`, `POST /api/advisor/ask`, `POST /api/project`,
`GET /api/shock_library`, `POST /api/cascade_trace`,
**`POST /api/policy_optimization`** (already exists — see note below),
plus the Experiment Studio CRUD set (`/api/experiments*`) and Notebook set
(`/api/notebooks*`).

**Important finding for Section 15's integration plan:** a
`/api/policy_optimization` endpoint already exists (`mb.run_policy_optimization`)
— this needs to be read and evaluated (not assumed to already implement
Section 10's full formulation) before any new optimisation endpoint is
built, to avoid duplicating existing work. This was not investigated
further this session and is flagged as the first concrete task for
whoever picks up Section 15's Phase 6.

**[PROPOSED] new/extended contracts for the Digital Twin:**

```
POST /api/policy/search
  body: { action_space: {...}, objective: "PAR"|"FPI"|..., 
          n_evaluations: int, scenario_context: {...} }
  returns: { best_policy: {...}, objective_value: float,
             search_trace: [...], attribution: {...} }
             # attribution reuses crisis_attribution(), Section 10

GET /api/policy/search/{search_id}
  returns: full PolicyRun history (queries the new policy_runs table)

POST /api/drivers/climate
  body: { node: str, rainfall_series: [...], temp_series: [...] }
  # [PROPOSED] ingestion endpoint for Section 6's continuous drivers,
  # once implemented — does not exist yet

GET /api/calibration/{variable_name}
  returns: { source_id, confidence_tier, last_validated }
  # surfaces the new calibration_sources table (Section 18) so a
  # frontend or API consumer can show calibration confidence inline,
  # directly addressing the "explainable" requirement from the prior
  # session's instruction
```

---

## 20. Future extension strategy

**Immediate (blocking) priority:** resolve the RC-amplification missing
negative feedback (Section 2). Every other item below is downstream of
this and should not be scheduled ahead of it.

**Near-term (Section 15 phases 3-5):** labour-availability production
term; the four [PROPOSED] environmental drivers (Section 6/7), *with* the
triple-counting redesign; the policy levers in Section 4, in the stated
cost-of-implementation order.

**Medium-term:** the optimisation loop (Section 10) and its supporting
schema/API work (Sections 18-19), gated on the above.

**Longer-term, explicitly out of scope for this specification:**
- A political-instability feedback loop (famine → rising unrest) — a
  deliberate scope boundary (Section 9), not an oversight; should be a
  dedicated, separately-scoped design exercise if wanted, not folded in
  incidentally.
- Sub-national spatial resolution — the current 35-node structure
  (21 countries + 14 regional blocs) is a genuine, documented trade-off
  (Phase 1 session finding); moving to sub-national resolution would be a
  fundamentally larger undertaking than any item in this document and
  should be scoped separately if the research group decides it's needed.
- A differentiable surrogate model for gradient-based optimisation —
  Section 10 argues black-box search is sufficient given current runtime;
  revisit only if that assumption is empirically found to be wrong.

**How to extend without breaking this architecture:** every new mechanism
should be checked against Section 2's causal graph before being added —
if it can be expressed as a modification to an existing state variable's
input (production, trade capacity, political risk, energy), it should be;
a genuinely new state variable (like Section 20's labour term) should be
rare, and each one added should come with the same four things every
[PROPOSED] item in this document has: an equation, a calibration source
with stated confidence tier, an affected-node/propagation description, and
a validation plan against real historical data before it is trusted for
policy search.

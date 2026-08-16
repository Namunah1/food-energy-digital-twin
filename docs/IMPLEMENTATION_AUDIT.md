# Implementation Audit — Current Codebase vs. Scientific Design Specification

**No code was modified to produce this document.** Every claim below is
traced to a specific file and line range, verified by direct reading this
session. Where I say something is real and working, I mean I read the
function body, not the docstring.

---

## PART 1 — Optimization / Policy Layer (the specifically-requested deep audit)

### 1.1 `POST /api/policy_optimization` → `model_bridge.run_policy_optimization()`

**Location:** `delivery/backend/app/model_bridge.py:983-1017`, wired at
`main.py:307-309`.

1. **What does it actually do?** Runs a **control** simulation (no policy
   response) plus **one simulation per atomic response lever** (5 levers,
   Section 1.2), all under the *same* fixed shock set supplied by the
   caller. Ranks the 5 levers by `population_saved_millions` (control PAR
   minus lever PAR).
2. **Which equations does it use?** None new — it calls the canonical
   `FoodEnergyModel`/`STCEngine` exactly as every other endpoint does, via
   `build_triggers_from_shocks()` (a UI-shock-to-trigger-dict translator,
   itself just reusing the existing trigger schema).
3. **Which state variables does it modify?** Whatever the selected
   `ATOMIC_RESPONSE_FN[key]` modifies (Section 1.2) — this function itself
   modifies none directly.
4. **Which objective does it optimise?** `population_saved_millions`
   (= control PAR − lever PAR) is the ranking key — this **is** the
   Section 10 objective (PAR), already the right choice, already wired.
5. **Global or local?** **Neither, in the search sense** — there is no
   search. It is an **exhaustive evaluation of 5 fixed, predefined,
   single-mechanism levers**, each tested in isolation against one fixed
   scenario. It does not combine levers, does not vary lever *intensity*
   (e.g. reserve mandate is always exactly 3 months, never optimised
   between 1-6 months), and does not vary which nodes a lever applies to
   (every lever is global-only, applied to all 35 nodes uniformly).
6. **Does it already implement any part of Section 10?** **Partially, and
   the useful part is real:** the objective function (PAR-based ranking)
   and the "run baseline vs. intervention, compare" harness are both
   directly reusable. **What's missing is the actual optimisation**: an
   action-space search over lever *combinations* and *intensities*, and
   any node-specific (as opposed to global-only) policy variables.
7. **Production-ready, partial, experimental, or a stub?** **Partial, but
   solid** — this is real, tested, working code (not a stub), just scoped
   to a much narrower problem (rank 5 fixed levers) than "policy
   optimisation" implies. Its own `note` field in the return payload is
   admirably honest about this: *"Only the 5 response levers with a real,
   distinct mechanism... are ranked here... not approximated."*
8. **Extend or rewrite?** **Extend.** The control/lever/PAR-comparison
   harness, the objective function, and the trigger-translation layer are
   all reusable as-is. What needs to be *added*, not replaced: (a) a
   combinatorial or continuous search over lever intensity and
   node-targeting, (b) the additional levers Section 4 lists that have no
   `ATOMIC_RESPONSE_FN` entry yet (aid, fertilizer redistribution, tariffs,
   adaptation funding, coordinated export restriction as a distinct
   lever from the existing ones).

### 1.2 Every existing policy-response function (the actual mechanisms Section 10 needs)

| Function | Location | What it does | State touched | Matches Spec Section |
|---|---|---|---|---|
| `_reserve_mandate` → `PoliticalEconomyModule.apply_reserve_mandate` | `scenarios.py:79-83`, `political_economy.py:315-329` | **One-time transfer** from `agent.reserves` into `agent.food_imperish`, capped at `min(reserves, gap)` — reclassifies existing stock, does not create new food | `reserves`, `food_imperish` | Partially implements §4 "reserve target" — **but is not the demand-anchored, ongoing-replenishment mechanism Section 4/Phase 2.5b §13.4 called for**, and is functionally **inert for the nodes that need it most**: a node with near-zero total reserves (Central Africa, per Phase 2.5's diagnostic) has nothing to transfer, so the mandate cannot manufacture reserves that don't exist |
| `_trade_diversification` → `apply_diversification` | `scenarios.py:85-113`, `political_economy.py:334-346` | Cuts `rho_ij` by 20% network-wide, boosts capacity on weakest 30% of edges by 25%, re-enables disabled edges | `network` edge attributes (`rho_ij`, `C_ij`, `active`) | Real, working implementation of a **global** (not corridor-specific) version of §B5 "shipping corridor protection" and part of §B3 |
| `_trader_regulation` → `apply_trader_regulation` | `scenarios.py:115-118`, `political_economy.py:303-311` | Reduces every trader's `market_share` by 15% | `PoliticalEconomyModule.traders[].market_share` | Not directly named in the Digital Twin spec — a genuinely distinct lever (speculation/margin control) worth adding to Section 4's lever table |
| `_transformational` | `scenarios.py:125-131` | Bundles the three above + boosts `agent.energy_renew ×1.40` (capped 200), zeroes `xi_biofuel` | All of the above + `energy_renew`, `xi_biofuel` | Partial implementation of §B7 "energy interventions" (a renewable push, not a release/subsidy) |
| `_renewable_push_only` | `model_bridge.py:212-222` | Isolated version of the renewable-push half of `_transformational` | `energy_renew`, `xi_biofuel` | Same as above, standalone |
| `_trader_regulation_only` | referenced in `ATOMIC_RESPONSE_FN`, defined in `model_bridge.py` (not re-quoted here) | Isolated trader-regulation lever | Same as `_trader_regulation` | — |

**None of Section 4's remaining levers exist yet**: food aid, fertilizer
redistribution, import tariff/subsidy, coordinated export restriction as
its *own* distinct lever (as opposed to bundled inside `_transformational`),
climate adaptation funding, and B1's *global pooled* reserve (as opposed
to the per-node mandate that exists). This confirms Section 4's
`[PROPOSED]` markings were correct for these specific levers, while the
three that exist should be re-marked "implemented" in a spec revision.

### 1.3 `crisis_attribution()` — the explainability function

**Location:** `scenarios.py` (viewed in full this session, prior turn).
**What it does:** for a completed model run, decomposes each overloaded
node's stress into food-stress / energy / contagion / reserve-failure
percentage shares, ranked by overload ratio. **Equations used:** reads
`FS_index`/`CC_index` component breakdown directly (Section 3 of the
causal decomposition) — not a new equation, a post-hoc decomposition of
existing state. **Modifies no state** — read-only. **Objective:** none —
it's a diagnostic, not an optimiser. **Status: production-ready**, already
used throughout this session's Phase 2 catalogue without incident.
**Extend or rewrite:** neither needed — Section 10's explainability
requirement should call this function as-is on the optimiser's top
candidates, exactly as recommended in the Digital Twin architecture doc.

### 1.4 `worst_case_discovery()` — a real search routine, but searching the wrong space for Section 10

**Location:** `scenarios.py:336-424`.
**What it does:** Monte Carlo random search — samples 50 random
*trigger* combinations (2-3 triggers each, random type/step/scope/
severity/target), runs each, ranks by a hand-weighted linear severity
score (`0.30×price_ratio + 0.25×U + 0.20×PAR/1000 + 0.25×n_overload/35`).
**Objective:** maximises severity (finds bad outcomes) — the **inverse**
of what Section 10 needs (minimise harm via good policy), but the
**sample → run → score → rank pattern is directly reusable
infrastructure** for a policy search: swap the sampled space from
trigger-parameters to Section 4's action-space variables, and flip the
ranking direction. **Status: production-ready** for its actual purpose
(adversarial scenario discovery); **not** itself a policy optimiser.
**Extend or rewrite:** extend — this is the closest existing thing to
Section 10's proposed black-box search *mechanism* (random sampling +
evaluation), even though its current *target* is different. A real
implementation of Section 10 could plausibly be `worst_case_discovery`'s
sampling loop retargeted at the policy action space, rather than a
new search implementation from scratch.

### 1.5 `sensitivity.py` (OAT / Morris / Sobol) — adjacent, not a policy search

**Location:** `sensitivity.py:123-560` (Phase 3 session's already-audited
territory; re-confirmed here). **What it does:** varies **calibrated
model parameters** (`RC_PRICE_AMPLIFICATION`, `EROI_DECLINE`, etc.) to
measure output sensitivity — this is a **scientific calibration tool**,
not a policy-lever search. **Objective:** variance decomposition, not
minimisation. **Status:** production-ready, already used for the Phase 3
validation report's RC-dominance finding. **Relevance to Section 10:**
none directly — flagged here only to explicitly rule it out, since its
name ("sensitivity analysis") could be confused with policy optimisation
by a new team skimming file names rather than contents.

### 1.6 `SHOCK_TYPE_MAP` / `build_triggers_from_shocks()` — a correction to the Digital Twin spec

**Location:** `model_bridge.py:199-211` (map), `~1020+` (translator, not
fully re-quoted).
**Finding that revises Section 6/Part D of the Digital Twin architecture
doc:** this map already includes **named entries for `pandemic`,
`fertilizer_shortage`, `shipping_disruption`, `war`, and
`currency_collapse`** — and critically, `stc_engine.py::_fire_trigger()`
(re-verified this session, `stc_engine.py:384-390`) has a **distinct,
already-implemented `"pandemic"` trigger type**, separate from
climate/geopolitical/speculative, that raises `agent.logistics_disruption`
for a randomly-sampled subset of nodes (`scope × 35` nodes) by `severity`.
**This means "pandemic" is not a gap** the way the Digital Twin
architecture document implied — it exists, and works through exactly the
`logistics_disruption` channel that document's Part D correctly
identified as the *right* existing hook, but incorrectly implied was not
yet wired up as a first-class trigger type. **What is still a genuine gap**
(the Digital Twin doc's other claim, which this finding does *not*
overturn): there is still no labour-availability term in the Cobb-Douglas
production function — the existing pandemic mechanism is entirely a
trade-side (logistics) effect, with no direct production-side effect from
worker illness/absence. `fertilizer_shortage`, `shipping_disruption`, and
`currency_collapse` map onto the existing `geopolitical`/`speculative`
types with preset multiplier defaults — real, working, but **not
mechanistically distinct** from a generic geopolitical/speculative shock;
they are labelled presets, not separate causal pathways. `war` is likewise
a labelled preset of the `geopolitical` type with higher default
multipliers, not a structurally distinct mechanism from `2022_ukraine_block`.

---

## PART 2 — Traceability matrix, all specification sections

| Spec Section | Existing File(s) | Function(s) | Current Status | Missing Components | Recommended Action |
|---|---|---|---|---|---|
| §2 Causal graph | `stc_engine.py`, `trade.py`, `prices.py`, `energy.py` | (whole-module, per Phase 2.5b) | **Fully audited, real** | RC-amplification negative feedback (Phase 2.5b §13.1); dead `_rc_contagion_boost`/`G_BASE` | Resolve feedback gap before any Section 10 work; remove or wire up dead code |
| §3 State variables (existing) | `agent.py`, `energy.py` | attribute-level, per Section 3 table | **Fully implemented** | — | None |
| §3 State variables (PROPOSED: soil, fertilizer, water) | none | none | **Not implemented** | All three | Build per architecture doc Parts C2-C4, in Section 15's stated order |
| §4 Policy variables | `scenarios.py`, `political_economy.py`, `model_bridge.py` | `_reserve_mandate`, `_trade_diversification`, `_trader_regulation`, `_transformational`, `_renewable_push_only` | **3 of 8 levers partially implemented** (reserve mandate, trade diversification/corridor, energy push); **trader regulation exists but wasn't in the spec's lever list at all** (add it) | Food aid, fertilizer redistribution, import tariff/subsidy, coordinated-export-restriction-as-distinct-lever, adaptation funding, global pooled reserve (vs. existing per-node mandate) | Extend `ATOMIC_RESPONSE_FN` with new entries for each missing lever, following the existing function signature pattern (`fn(model) -> None`, mutating agent/network state directly) |
| §5 Global variables | `energy.py`, `stc_engine.py` | `_eroi_penalty_global`, `_cascade_active_until` | **2 of 4 implemented**; `R_global` and new exogenous indices not implemented | `R_global` (reserve pool), fertilizer/shipping global indices | Build `R_global` alongside the reserve-mandate redesign (§4) since they're related concepts |
| §6 Climate variables | `agent.py::_update_climate_modifier`, `stc_engine.py` climate trigger | discrete only | **Discrete/trigger-only implemented**; continuous driver not implemented | Continuous rainfall/temperature process; triple-counting resolution | Do not add continuous drivers until triple-counting (Phase 2.5b) is resolved — same order Section 15 already specifies |
| §7 Resource variables | `agent.py` (land, water, energy) | Cobb-Douglas inputs | **3 of 5 implemented** (land, water, energy); fertilizer and water-*stock* (as opposed to static index) not implemented | Φ_i (N/P/K), W_stock,i | Build per architecture doc Part C3/C4; note existing static `fertiliser_kg_ha` (used once, at calibration time only) is *not* reusable as the live Φ_i state — genuinely new |
| §8 Trade variables | `trade.py`, `network_weights.csv` | `_gravity_volume`, `_propagate_export_ban` | **Fully implemented** | Per-edge/per-node price (currently single global scalar) — flagged as a known simplification, not a missing feature per se | None required unless bilateral pricing is explicitly wanted |
| §9 Geopolitical variables | `agent.py`, `trade.py::_effective_risk` | static `political_risk`/`rho_ij` + `sanction_penalty` overlay | **Fully implemented** (as a static-input design, deliberately) | Dynamic political-instability feedback (explicitly out of scope, Section 20) | None — confirmed correct as designed |
| §10 Optimisation objective | `model_bridge.py::run_policy_optimization`, `scenarios.py::worst_case_discovery` | see Part 1.1/1.4 above | **Objective function (PAR) and evaluation harness exist; the actual search does not** | Combinatorial/continuous action-space search; node-specific policy targeting | **Extend, do not rewrite** — see Part 1.1 point 8 |
| §11 Constraints | none | none | **Not implemented** — no cost model for any lever | Cost-per-unit for every policy lever | New data-sourcing task (FAO/World Bank cost literature), independent of code work |
| §12-14 Calibration/validation/data sources | `docs/DATA_PROVENANCE.md`, `retrodiction.py` | — | **Fully implemented for existing variables**; per-driver tiering in spec is new-analysis, not new code | New sources for Part C drivers | Data acquisition, not implementation, is the blocker |
| §15 Integration plan | — | — | **This document (the audit) is the first deliverable of the plan; nothing past step 0 has started** | — | Proceed per the stated order once RC-amplification (§2) is resolved |
| §16 Equations | `stc_engine.py`, `agent.py`, `prices.py` | — | **Fully implemented, verified against source this session** | — | None |
| §17 Software architecture | `delivery/backend/app/*.py`, `delivery/frontend` | FastAPI app, Next.js | **Current state fully implemented**; K8s/queue target architecture is **[PROPOSED]**, per Phase 5 | Job queue, KEDA autoscaling, Postgres migration | Per Phase 5 deployment doc, independent of scientific work |
| §18 Database schema | `experiment_store.py`, `notebook_store.py` | `CREATE TABLE experiments` | **Current single-table schema implemented and in use** | `node_timeseries`, `policy_runs`, `calibration_sources` tables | New migration, additive (spec already designed to extend, not replace) |
| §19 API contracts | `main.py` | ~30 real endpoints, **including `/api/policy_optimization` already** | **Far more already implemented than the spec assumed** — this whole Part 1 is the correction | `/api/policy/search` (the real optimiser), `/api/drivers/climate`, `/api/calibration/{var}` | Extend `main.py`/`model_bridge.py` following the existing endpoint pattern once the underlying search (§10) exists — building the endpoint before the search it calls would be premature |
| §20 Future extension strategy | — | — | Guidance document, not code | — | No action — revisit as each dependency above is resolved |

---

## PART 3 — What this audit changes about the Scientific Design Specification

1. **Section 4's lever table needs three rows changed from `[PROPOSED]` to
   "partially implemented"** (reserve mandate, trade diversification,
   renewable push), each with the specific limitation found here (the
   reserve mandate's inertness for zero-reserve nodes, in particular,
   should be called out explicitly wherever Section 4 is used to plan
   further work — it is not a blank slate, it is a real mechanism with a
   real, diagnosed weakness).
2. **Section 19 undersold the existing API surface** — `/api/policy_optimization`
   already exists and already returns a PAR-ranked comparison. The correct
   framing for future work is "extend this endpoint's underlying search,"
   not "build policy search from nothing."
3. **Part D of the architecture document (crisis types) undersold
   `pandemic`'s implementation status** — it has a real, distinct trigger
   type, not just a routing through geopolitical/speculative presets. The
   genuinely open item (no labour term in production) stands, but the
   framing should be "the trade-side pandemic effect is real and
   implemented; the production-side effect is the actual gap," not
   "pandemics are unimplemented."
4. **`worst_case_discovery` should be named explicitly in Section 10** as
   the closest existing infrastructure to the proposed search mechanism —
   omitting it risked a future team re-implementing a random-sample-and-
   rank harness that already exists in a closely related form.
5. **No finding in this audit changes Section 2's priority ordering** —
   the RC-amplification negative-feedback gap remains the correct blocking
   item before Section 10 work, regardless of how much of the evaluation
   harness around it already exists.

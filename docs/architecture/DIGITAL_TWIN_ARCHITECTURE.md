# Digital Twin Architecture — Scientific Specification
## Global Food-System Policy Optimisation Platform

**Status: design only, per your instruction — no code in this document.**
Every mechanism proposed here is explicitly anchored to a specific
existing hook identified in `PHASE2_5B_CAUSAL_DECOMPOSITION.md`, so new
drivers extend the causal graph rather than sitting beside it. Where no
real data source exists yet, that is stated plainly rather than implied.

---

## PART A — Per-node variable taxonomy

This section reclassifies every state and parameter already present in
`agent.py`/`energy.py` (Phase 2.5b) into the six categories you asked for,
and adds the specific new variables needed for the expanded environmental
system (Part C). Nothing already covered in Phase 1/2.5b is redefined —
only reclassified and, where genuinely new, added.

### A1. Endogenous state variables (evolve from the model's own dynamics)

| Variable | Symbol | Currently exists? | Governing equation |
|---|---|---|---|
| Population | P_i(t) | Yes | `update_population()`, §9 |
| Capital | K_i(t) | Yes | `update_capital()`, §10 |
| Technology | T_i(t) | Yes | capped logistic growth, §10 |
| Food stocks (imperishable/perishable/animal) | F_i(t) | Yes | `_produce_*`, `_consume_food` |
| Strategic reserves | R_i(t) | Yes | `_replenish_reserves()` |
| Food security ratio | σ_i(t) | Yes | `compute_food_security()` |
| FS_index / CC_index | Yes | Yes | STC engine, §3/§5 of Phase 2.5b |
| Energy stress index | ES_i(t) | Yes | `EnergyModule._compute_es_index` |
| Biofuel land share | ξ_i(t) | Yes | Arrow 2 coupling |
| Export fraction / export ban | Yes | Yes | 3-regime policy, §11 |
| **NEW: Soil quality index** | Q_soil,i(t) | No | Part C2 |
| **NEW: Cumulative fertilizer application (N/P/K)** | Φ_i(t) | No | Part C3 |
| **NEW: Water table / reservoir stock** | W_stock,i(t) | No | Part C4 |

### A2. Exogenous drivers (external time series, not produced by the model)

| Variable | Currently exists? | Proposed source |
|---|---|---|
| FAO Food Price Index (retrodiction anchor) | Yes | `fpi_monthly_1990_2026.csv` |
| Global oil/EROI trend | Partial (hand-set decline rate) | IEA World Energy Outlook |
| **NEW: Rainfall / precipitation anomaly** | No | CHIRPS or GPCC (Part C1) |
| **NEW: Temperature anomaly** | No | Berkeley Earth / NOAA GHCN (Part C1) |
| **NEW: Global fertilizer price index** | No | World Bank Commodity Markets ("Pink Sheet") |
| **NEW: Global shipping freight index** | No | Baltic Dry Index / UNCTAD |

### A3. Controllable policy variables (the action space for optimisation)

These map directly onto existing model hooks identified in Phase 2.5b —
this is the single most important design constraint: **the optimiser
should search over variables the model already listens to**, not invent
new ones.

| Policy lever | Node-level or global? | Existing hook (Phase 2.5b §14) |
|---|---|---|
| Export fraction cap override | Node | `agent.export_fraction`, `mu_i` |
| Strategic reserve target | Node | `RESERVE_RATIO` / reserve target (flagged for redefinition, §13.4) |
| Reserve release (emergency) | Node | Direct `reserves` injection, same pathway as `_replenish_reserves` in reverse |
| Sanction / trade-risk penalty | Edge (bilateral) | `sanction_penalty` → `rho_ij` |
| Import tariff / subsidy | Node | New: affordability multiplier on `_gravity_volume`'s `affordable_kcal` term |
| Fertilizer allocation | Node | Routes through `epsilon_ef`/A_i via energy-food coupling (Phase 2.5b Arrow 1), extended in Part C3 |
| Climate adaptation investment | Node | Reduces `drought_index`/`heatwave_index`/`flood_index` sensitivity (Part C1) |
| Food aid transfer | Node-to-node | New: direct stock transfer bypassing the gravity model's affordability constraint (Part B2) |

### A4. Uncontrollable environmental variables

| Variable | Governing subsystem |
|---|---|
| Drought / heatwave / flood indices (current) | §9, Phase 2.5b |
| **NEW: Rainfall anomaly** | Part C1 |
| **NEW: Temperature anomaly** | Part C1 |
| **NEW: Soil degradation trend** | Part C2 |
| Political risk (ρ_i, ρ_ij) — static baseline | §10, Phase 2.5b (only the *penalty* on top is controllable, not the baseline) |

### A5. Trade dependencies

Already fully represented: the 35×35 directed network (`network_weights.csv`,
`C_ij`, `κ_ij`, `ρ_ij`) *is* the trade-dependency structure. No new
representation needed — policy levers act on this existing structure
(edge capacity, edge risk) rather than requiring a parallel one.

### A6. Resource dependencies

| Resource | Currently represented? | Gap |
|---|---|---|
| Land (arable) | Yes (`L_i`) | — |
| Water | Yes (`W_i`, Cobb-Douglas input) | No distinction between renewable/non-renewable water stock (Part C4) |
| Energy (fossil/renewable/electric) | Yes | — |
| **Fertilizer (N/P/K)** | **No** — only static `fertiliser_kg_ha` used once for T_i calibration | Part C3 closes this gap |
| **Phosphorus specifically** | **No** | Part C3 (phosphorus is geologically concentrated — Morocco holds ~70% of known reserves — making it a distinct systemic-risk resource from N/K, which are more distributed; this asymmetry should be represented explicitly, not folded into a generic "fertilizer" scalar) |

### A7. Resilience indicators

Already computed (Phase 1/3): CC_index, reserve-months, baseline
undernourishment. For the Digital Twin's optimisation objective (Part D),
these become the **outcome metrics being minimised**, not just descriptive
statistics — no new indicator is needed, but their role shifts from
"reported" to "optimised against."

---

## PART B — Global-level policy levers

Each lever below is specified as a modification to an **existing**
equation or variable (per Phase 2.5b's integration principle), not a new
free-standing mechanism.

### B1. FAO strategic reserves (coordinated, multi-node reserve pool)

**Mechanism:** a new global pool variable `R_global(t)`, replenished by a
configurable levy on nodes above a σ threshold (analogous to the existing
3-regime export logic, applied to reserve contribution instead of trade)
and drawn down by request from nodes below `σ_safe_i`. **Equation:**
`R_global(t+1) = R_global(t) + Σ_i levy_i(t) − Σ_i draw_i(t)`, where
`levy_i(t) = λ × max(0, σ_i − σ_safe_i) × D_i` (λ = policy parameter) and
`draw_i(t) = min(request_i, R_global(t) / n_requesting)`.
**Affected variables:** `agent.reserves` (recipient nodes), a new
model-level accumulator.
**Propagation:** identical channel to existing reserve mechanics (Section
A8, Phase 2.5b) — draws feed directly into `compute_food_security()`'s
`R_draw` term, so no new propagation logic is needed, only a new source.

### B2. International food aid

**Mechanism:** direct node-to-node stock transfer that **bypasses** the
gravity model's affordability constraint (`_gravity_volume`'s
`affordable_kcal` term) — this is the correct, minimal way to represent
aid as economically distinct from trade, since aid is precisely trade
without the affordability gate. **Equation:** `aid_ij(t) = policy-set
volume`, applied as `donor.food_imperish −= aid; recipient.food_imperish
+= aid`, functionally identical to the transfer block in
`execute_trade_step()` but skipping the `_gravity_volume` computation
entirely.
**Affected countries:** donor/recipient pairs specified by the policy
search, not restricted to existing high-capacity trade edges (aid can flow
where trade infrastructure doesn't, e.g. via air/humanitarian corridors) —
this argues for a *separate* edge set from `network_weights.csv`, not
reuse of it.

### B3. Coordinated export restrictions

**Mechanism:** this is already fully representable via the existing
3-regime export policy (§11) — a "coordinated" restriction is simply
setting `export_fraction` caps below `mu_i` for a policy-selected set of
nodes simultaneously. **No new mechanism required.** The only addition
needed is a policy-layer wrapper that applies the same override to
multiple nodes in one call, and — importantly — **should also route
through `_propagate_export_ban`'s existing contagion logic** so a
coordinated restriction's knock-on effects on non-participating nodes are
modelled consistently with unilateral bans, not treated as a separately-
calibrated mechanism.

### B4. Fertilizer redistribution

**Mechanism:** direct transfer of `Φ_i(t)` (Part C3's new fertilizer-stock
variable) between nodes, structurally identical to B2 (aid) but acting on
the new fertilizer state rather than food stock. **Propagation:** through
Part C3's fertilizer→A_i channel, i.e. redistribution changes downstream
production via the *same* pathway a fertilizer shortage or export ban
would use (Phase 2.5b's finding that fertilizer currently has no live
state — Part C3 is a prerequisite for this lever to mean anything beyond
a relabelled energy shock).

### B5. Shipping corridor protection

**Mechanism:** targets `edge_data['C_ij']` and `seller.logistics_disruption`/
`buyer.logistics_disruption` directly (Phase 2.5b's finding: these
attributes already exist in `_gravity_volume` but are not yet exposed as a
first-class policy or trigger target). **Equation:** protection reduces
`logistics_disruption` for specific edges/nodes by a policy-set amount,
directly increasing `cap_volume = edge_cap × (1−κ) × (1−logistics_factor)`.
**Affected countries:** whichever edges route through a named corridor
(e.g. Suez, Black Sea, Strait of Hormuz) — this requires a new mapping
from named corridors to the specific edges in `network_weights.csv` that
pass through them, which does not currently exist and would need to be
constructed (a real, non-trivial data task — flagged, not hand-waved).

### B6. Climate adaptation funding

**Mechanism:** reduces a node's *sensitivity* to climate shocks rather
than the shocks themselves — i.e. modifies the coefficients in
`_update_climate_modifier()` (currently fixed at 0.40/0.35/0.25 for
drought/heatwave/flood) on a per-node basis as a function of cumulative
adaptation investment. **Equation:** `coefficient_i(t) = base_coefficient
× (1 − adaptation_effectiveness × cumulative_investment_i(t) /
investment_saturation)`, logistic-saturating (consistent with the
existing technology-growth saturation pattern in `update_capital()`, §10,
reusing an already-validated functional form rather than inventing a new
one).
**Calibration risk:** `adaptation_effectiveness` has no obvious empirical
anchor in the current data sources — flagged for Part E as the single
policy lever with the weakest calibration prospects.

### B7. Energy interventions (strategic petroleum release, subsidies)

**Mechanism:** directly targets `EnergyModule._energy_price` and/or
`agent.energy_fuel`, i.e. the existing shock interface
(`apply_energy_shock`, Phase 2.5b §7) run in reverse — a release is a
negative-severity supply-cut shock, a subsidy is a negative-severity
price-spike shock. **No new mechanism required** — this is the cleanest
lever to implement because it reuses an interface that already exists for
shocks in the opposite direction.

### B8. Emergency reserve release (global trigger, distinct from B1's steady-state pool)

**Mechanism:** a one-time, policy-triggered draw from B1's `R_global`,
distributed by need (`σ_i` ranking) rather than request — this is a
*rule*, not a new state variable, layered on top of B1.

---

## PART C — Expanded environmental driver system

### C1. Rainfall, drought, temperature anomalies

**Current state:** `drought_index`, `heatwave_index`, `flood_index` exist
as per-agent scalars but (per Phase 2.5b) their persistence/decay behaviour
was flagged as unconfirmed, and they are currently only set by discrete
trigger injection, not by a continuous driver process.

**Proposed equations:**
`drought_index_i(t) = clip((rainfall_climatology_i − rainfall_i(t)) / rainfall_climatology_i, 0, 1)`
`temp_anomaly_i(t)` feeds a new `heat_stress_i(t) = clip((temp_anomaly_i(t) − heat_threshold) / heat_range, 0, 1)` replacing the currently trigger-only `heatwave_index`.

**Affected variables:** `climate_modifier` (existing, §9), and via Phase
2.5b's already-documented triple-counting, production, FS_index, and
ES_index simultaneously — **this expansion must be introduced alongside
the triple-counting redesign flagged in Phase 2.5b §13.5, not before it**,
or the effect of a continuous rainfall driver will be counted three times
per tick by construction.

**Affected countries:** all 35 nodes, but with real heterogeneity —
rainfall variability matters far more for rain-fed agriculture (most of
Sub-Saharan Africa, South Asia) than for irrigation-dominant or
water-scarce-by-design systems (Saudi Arabia, Egypt, already water-input-
dominated per Phase 1's W_i documentation) — the *sensitivity coefficient*
to rainfall anomaly should vary by each node's irrigation share, which is
not currently in the dataset and would need sourcing (FAO AQUASTAT has
irrigated-area-share by country).

**Propagation mechanism:** identical to existing climate triggers — no new
propagation pathway, only a new, continuous (rather than discrete-trigger-
only) source for the same `climate_modifier` input.

**Calibration data sources:** CHIRPS (Climate Hazards Group InfraRed
Precipitation with Station data, UCSB) for rainfall, 1981–present, ~0.05°
resolution, aggregable to country level; Berkeley Earth or NOAA GHCN for
temperature anomalies, both public and station-validated. Neither is
currently in `data/raw/`.

**Expected uncertainty:** rainfall→yield relationships are genuinely
heterogeneous by crop and region in the agronomic literature; a single
national-average drought index (as currently structured) will understate
uncertainty for large, climatically heterogeneous nodes (China, US, the
regional blocs especially) — this should be documented as a known
resolution limitation, not resolved by faking sub-national granularity the
data doesn't support at this model's current spatial resolution.

### C2. Soil quality

**Current state:** does not exist at all — not even as a static input,
unlike land area (`L_i`) which is a pure quantity with no quality
dimension.

**Proposed equation:** `Q_soil,i(t+1) = Q_soil,i(t) + regen_rate × (1 −
Q_soil,i(t)) − degradation_rate × intensity_i(t)`, where
`intensity_i(t)` is a function of current land-use intensity (proxy:
production per hectare relative to node's own historical baseline).
**Affected variables:** enters the Cobb-Douglas production function
(§9, Phase 2.5b) as a new multiplicative term, analogous to `climate_modifier`.
**Calibration data sources:** FAO's Global Soil Organic Carbon map, or the
ISRIC SoilGrids dataset — both public, though neither has a clean,
pre-aggregated time series comparable to this project's other FAO/OWID
sources; this would require new data-pipeline work, not just a new column.
**Expected uncertainty:** high — global soil-quality time series at
national resolution are genuinely sparse; this driver should be introduced
initially as a *slow, mostly static* modifier (closer to how climate_vuln
currently behaves — static per Phase 2.5b §10's finding) rather than a
fully dynamic state, until real degradation-rate data can be sourced.

### C3. Fertilizer availability (N/P/K) — closing the gap Phase 2.5b B3 flagged

**Proposed state:** `Φ_i(t) = (N_i(t), P_i(t), K_i(t))`, three separate
stocks (not one scalar), because phosphorus specifically has a distinct
systemic-risk profile (geologically concentrated — see A6) from nitrogen
(synthesized from natural gas, so already indirectly represented via the
energy-food coupling) and potash (also geologically concentrated, distinct
producer set from phosphorus).

**Proposed equation:** replaces the current *proxy* routing (Phase 2.5b's
finding that fertilizer bans are currently modelled only via the energy
channel) with a direct multiplicative term in the Cobb-Douglas production
function: `A_i_eff(t) = A_i(t) × (1 − ε_EF×ES_i(t)) ×
f(Φ_i(t)/Φ_i_reference)`, where `f(·)` is a saturating function
(diminishing returns to fertilizer application, consistent with the
agronomic literature — e.g. a Mitscherlich-type response curve) rather
than linear, so that below-reference application is penalised more
steeply than above-reference application is rewarded.

**Affected countries:** import-dependent fertilizer nodes (most of
Sub-Saharan Africa and South Asia import the majority of their N/P/K) are
structurally distinct from producer nodes (China, Russia, US for nitrogen;
Morocco, China for phosphorus; Canada, Russia, Belarus for potash) — this
argues for a **second, fertilizer-specific trade network**, structurally
parallel to `network_weights.csv` but with different edge weights (a
different, smaller set of major exporters), not a re-use of the food
trade network's capacities.

**Calibration data sources:** IFA (International Fertilizer Association)
publishes country-level N/P/K consumption and trade statistics; World
Bank's `AG.CON.FERT.ZS` (already used once, statically, per
`DATA_PROVENANCE.md`) could be extended to its full time series rather
than a single-year snapshot.

**Expected uncertainty:** moderate for aggregate N/P/K flows (well-tracked
commodity), higher for the production-response function `f(·)`, since
fertilizer-yield elasticity varies enormously by existing soil fertility
(interacting with C2) and crop type — flagged as a joint calibration
challenge with Part C2, not independently resolvable.

### C4. Water availability (distinct from the existing static W_i)

**Current state:** `W_i` is a single, static Cobb-Douglas input (β=0.25)
— per Phase 1's data dictionary, sourced from a water-availability index,
not a stock that can be drawn down or replenished.

**Proposed equation:** introduce `W_stock,i(t)` as a genuine reservoir/
water-table state: `W_stock,i(t+1) = W_stock,i(t) + rainfall_i(t) −
withdrawal_i(t) − evaporation_i(t)`, with `withdrawal_i(t)` a function of
agricultural + industrial + municipal demand (only the agricultural share
directly affects this model's production function). The existing static
`W_i` becomes this new state's *initial condition* and long-run mean, not
a replacement.
**Calibration data sources:** World Bank `ER.H2O.FWTL.ZS` (already in
`DATA_PROVENANCE.md` as WB-WS, currently used statically) extended to a
genuine time series; FAO AQUASTAT for withdrawal breakdowns by sector.
**Expected uncertainty:** groundwater depletion specifically (as opposed
to surface water) is poorly observed globally except via GRACE satellite
gravimetry data, which exists but at coarse spatial resolution relative to
national boundaries — flagged as a known limitation for water-stressed
nodes (Saudi Arabia, Egypt, per Phase 1) where groundwater/aquifer
depletion is the dominant real-world risk, not just annual rainfall
variability.

### C5. Crop productivity

**Not a new driver** — this is the existing Cobb-Douglas `A_i` (TFP)
already documented extensively in Phase 1/2/3. Listed here only to confirm
it does not need duplication: rainfall (C1), soil (C2), fertilizer (C3),
and water (C4) all enter as *inputs* to production; A_i remains the
residual TFP term capturing management practices, crop genetics, and
everything not explicitly modelled by the other four.

---

## PART D — Quantitative representation of crisis types (not disconnected heuristics)

Per your explicit instruction, each of these must be a parameterisation of
**existing** variables, cross-referenced to Phase 2.5b's integration table
(§14) rather than a new mechanism per crisis type.

| Crisis type | Existing variable(s) modified | NOT a new mechanism because |
|---|---|---|
| War | `export_fraction`, `sanction_penalty` (via edges touching the combatants), `logistics_disruption` on affected corridors | Identical pathway to the existing `2022_ukraine_block` trigger — a war is a parameterised, possibly longer-duration and broader-scope version of that same trigger type |
| Sanctions | `sanction_penalty` → `rho_ij` (edge-level) | Direct use of the hook Phase 2.5b confirmed exists and is currently unused-by-default |
| Pandemic | `logistics_disruption` (broad, low-severity, long-duration — distinct signature from a war's narrow-high-severity pattern), plus a new labour-availability multiplier on `annual_production` (not currently present — genuine gap: production currently has no labour term at all, only land/water/energy/technology per the Cobb-Douglas form) | Requires one genuinely new production-function term (labour availability), everything else reuses existing logistics/trade friction |
| Port closures | `edge_data['C_ij']` (capacity reduction on specific edges), `logistics_disruption` | Same mechanism as B5 (shipping corridor protection) run in the damaging direction — protection and closure are the same lever, opposite sign |
| Supply-chain disruption (general) | Whichever specific variable the disruption actually targets (fertilizer→Φ_i, energy→energy_fuel, food→C_ij) | This is a category label, not a mechanism — "supply chain disruption" should never be its own trigger type in the code; it should always be resolved to one of the above at the point of scenario design, exactly as this session's Phase 2 catalogue already did for the 2019-20 COVID trigger (routed through trade-disruption scope/severity, not a generic "supply chain" flag) |

**The one genuine gap this section surfaces:** production currently has
**no labour term**. A pandemic's primary real-world transmission mechanism
into food production (workers sick, in quarantine, or dead) has no home in
the current Cobb-Douglas formulation (land/water/energy/technology only).
Adding a labour availability multiplier is a small, well-precedented
extension (same functional slot as the climate_modifier `C` term) but is
a genuinely new state variable, not a re-routing of an existing one — the
only such case in this entire Part D.

---

## PART E — Calibration strategy

1. **Reuse the existing Phase 3 CC_index precedent** (ML regression against
   FAO undernourishment, cross-validated) as the template for any new
   composite index this expansion introduces (e.g. the fertilizer
   production-response function `f(Φ)` in C3) — that is the only
   subsystem in the current model with genuine, documented, cross-
   validated empirical grounding, and new mechanisms should be held to the
   same bar, not a lower one.
2. **Tier new drivers by calibration confidence**, and say so explicitly in
   any published scenario using them:
   - **High confidence** (established, long time-series, direct fit): rainfall/temperature (C1), fertilizer N/P/K trade flows (C3's flow side).
   - **Medium confidence** (real data exists but response function is uncertain): fertilizer production-response curve, water withdrawal/depletion (C4).
   - **Low confidence** (no direct data source identified in this session): climate-adaptation effectiveness (B6), soil degradation rate (C2), labour-availability sensitivity to pandemics (Part D).
3. **Do not backfill low-confidence parameters with the ML-regression
   approach used for CC_index** — that approach worked because FAO
   undernourishment is a real, independent target series to regress
   against; several of the new levers (adaptation effectiveness
   specifically) have no comparable independent outcome series available,
   and forcing an ML fit without one would produce a spuriously precise-
   looking number with no real validation, the same failure mode already
   flagged for JOURNAL_PAPER.md's stale claims in the Phase 3 report.

---

## PART F — Integration and propagation architecture

**Design principle, stated once, applying to every driver above:** every
new variable enters the causal graph exactly where Phase 2.5b's diagram
shows the corresponding existing quantity entering — production, ES_index,
FS_index, or trade capacity — so that a policy change at one node
propagates through the *existing* trade network and price-feedback loop
(Phase 2.5b §11) automatically, without a separately-coded propagation
step per driver. Concretely:

- Any node-level policy or environmental change first modifies one of:
  `A_i` / production inputs, `export_fraction`, `energy_fuel`/`ES_index`,
  or edge-level `C_ij`/`rho_ij`.
- From there, the existing chain (production → σ → FS_index/CC_index →
  overload → RC price shock → global price → every other node's FS_index)
  carries the effect network-wide with no new code path required.
- **The one exception is B2 (food aid) and B4 (fertilizer redistribution)**,
  which deliberately bypass the trade network's affordability gate — these
  need a clearly separate, explicitly-flagged transfer pathway precisely
  *because* they are meant to act differently from market-mediated trade,
  not because the existing propagation mechanism is insufficient.

This is also why Phase 2.5b's still-open finding (RC price amplification's
missing negative feedback, its Section 13.1) is a **blocking prerequisite**
for policy optimisation, not a parallel workstream: an optimiser searching
over the policy variables in Part A3/Part B will, by construction, route
every candidate policy's effect through that same unbounded loop. Until it
has a genuine negative feedback term, an optimisation objective (Part G)
would be searching a landscape where many candidate policies look
artificially catastrophic or artificially benign depending on how close
they happen to push the system toward the loop's activation threshold,
rather than reflecting the policy's real merit.

---

## PART G — Policy optimisation formulation

**State space:** the full per-node vector in Part A1/A2 across all 35
nodes, plus the two new global pools (B1's `R_global`).

**Action space:** the controllable variables in Part A3 and the global
levers in Part B, each with realistic bounds (e.g. export fraction ∈
[0, μ_i], reserve levy λ ∈ [0, reasonable max]).

**Objective function (minimise):** a weighted combination of the existing
resilience indicators (Part A7) — most naturally, total population-at-risk
(PAR) across all 35 nodes over the scenario horizon, already computed by
`metrics.py`, or a food-security-weighted variant (e.g. Σ_i P_i ×
max(0, σ_safe_i − σ_i)) — no new metric needs to be invented; the
optimisation target should be one of Phase 3's already-validated retro-
diction metrics (PAR passed 3/4 scored episodes even under the current,
imperfect FPI fit) rather than the FPI metric that Phase 2.5b showed is
downstream of the unresolved RC-amplification issue.

**Constraint set:** budget constraints on policy levers with real-world
cost analogues (reserve levy, aid volume, adaptation funding) — these
costs are not currently represented anywhere in the model and would need
their own calibration (e.g. USD cost per kcal of strategic reserve held,
per FAO/World Bank cost-of-storage literature) before a genuine
cost-constrained optimisation (as opposed to an unconstrained "minimise
harm regardless of cost" search) is meaningful.

**Search approach:** given the model's demonstrated per-run cost (~1
second/replica, Phase 2 session), a derivative-free, black-box optimiser
(e.g. Bayesian optimisation or an evolutionary strategy over the Part A3/B
action space) is computationally tractable without needing the simulator
itself to be differentiable — this should be confirmed as sufficient
before considering a heavier approach (e.g. differentiable surrogate
modelling), since the latter is a much larger engineering investment this
architecture does not yet justify needing.

**Explainability requirement (your stated goal — "explainable effects on
every other node"):** this is directly served by the existing
`crisis_attribution()` function (Phase 2 session, `scenarios.py`) —
already produces a per-node decomposition of overload cause (food-stress
share, energy share, contagion share, reserve-failure share). No new
explainability mechanism needs to be built; the optimisation loop should
simply call this existing function on its top candidate policies, not
invent a parallel attribution system.

---

## Summary of new state that would need to be added (implementation phase, not this document)

1. Labour-availability term in production (Part D) — the one truly new
   Cobb-Douglas input.
2. `Φ_i(t) = (N_i, P_i, K_i)` fertilizer stocks + a second, fertilizer-
   specific trade network (Part C3).
3. `Q_soil,i(t)` soil quality state (Part C2).
4. `W_stock,i(t)` water reservoir state, distinct from the existing static
   `W_i` (Part C4).
5. Continuous rainfall/temperature-anomaly driver processes replacing the
   current trigger-only drought/heatwave indices (Part C1) — **contingent
   on resolving Phase 2.5b's triple-counting finding first**.
6. `R_global(t)` coordinated reserve pool + a separate aid-corridor edge
   set distinct from `network_weights.csv` (Parts B1/B2).
7. A resolved RC-amplification negative feedback (Phase 2.5b, carried
   forward here as a hard prerequisite, not optional polish) before any
   of the above should be used for actual policy search.

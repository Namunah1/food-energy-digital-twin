# Phase 2.5b — Causal Decomposition of the Simulator

**Scope note:** this document does not attempt to improve validation and no
calibrated parameter was touched while producing it (including
`RC_PRICE_AMPLIFICATION`, per your explicit instruction). Every equation,
constant, and code reference below is taken directly from the current
merged codebase (post Phase 2.5 sequencing fix). Where a mechanism is
non-functional despite being present in the code, that is stated plainly
rather than smoothed over — it matters directly for how future features
should be wired in.

---

## 1. RC Price Amplification

- **Inputs:** `n_food_overloaded` (current count of nodes with FS/CC>threshold), compared against `self._n_overloaded_food_last` (previous tick's count).
- **Outputs:** a direct multiplicative shock to `model.price_system.price`; sets `model._cascade_active`, `model._rc_contagion_boost`, `self._cascade_active_until = t + RC_DURATION_STEPS`.
- **State variables:** `STCEngine._cascade_active_until` (int, persists across ticks); `model._cascade_active` (bool); `model._rc_contagion_boost` (float).
- **Equation:** fires only when `n_food_overloaded > n_overloaded_food_last`; `factor = 1 + RC_PRICE_AMPLIFICATION × n_food_overloaded` (0.021 per node currently), applied via `price_system.shock(factor)`.
- **Parameters:** `RC_PRICE_AMPLIFICATION = 0.021`, `RC_DURATION_STEPS = 4`, `RC_CONTAGION_BOOST` (magnitude — see finding below).
- **External dependencies:** `_detect_overload()`'s output (itself downstream of FS_index/CC_index, Section 3/5); `PriceSystem.shock()`.
- **Positive feedback (the dominant loop in the whole model):** more overloaded nodes → price shock → `_compute_FS_index()`'s `(1 + max(0, p_ratio−1))` term raises FS_index for every node using that price ratio → more nodes cross the overload threshold next tick → larger `n_food_overloaded` → larger shock. This loop has no counteracting term *within the mechanism itself*.
- **Negative feedback:** none intrinsic to this mechanism. The only brakes are external: `PriceSystem`'s hard clamp (`PRICE_CEILING = 5.00`) and its `REVERSION_RATE=0.04` mean-reversion pull toward `p_adaptive` (rolling 5-step mean).
- **Time delays:** `RC_DURATION_STEPS=4` — the *contagion boost* window persists 4 steps once activated, but see the finding directly below: this window currently gates nothing.
- **Saturation:** entirely borrowed from `PriceSystem` (0.80–5.00 clamp), not from this mechanism.
- **Hidden coupling — two findings, not previously documented anywhere in the repo:**
  1. **`model._rc_contagion_boost` and `model._cascade_active` are set here but never read anywhere else in the codebase** (confirmed by grep across every `.py` file). The "Rigidity Cycle contagion boost" described in this module's own docstrings and in `EQUATIONS.md` is **dead code** — it computes a value that no other subsystem consumes. Only the direct price-shock half of RC amplification is functionally real.
  2. `PriceSystem.update()`'s `p_adaptive` reversion target is the rolling mean of `price_history[-5:]`, and `shock()` appends directly to that same `price_history` list. When a shock fires and `update()` runs immediately after in the same tick, the "stabilizing" reversion target is partly computed from the very shock it's supposed to counteract — weakening the negative feedback exactly when it's needed most.
- **Assessment:** structurally correct in intent (Homer-Dixon RC framework), but (a) half its effect (contagion boost) is inert, and (b) it is the primary mechanism identified as **capable of producing unrealistic runaway behaviour** — directly responsible for the stability-test near-ceiling saturation found after the Phase 2.5 sequencing merge (Section 6 of the merge change report). Not empirically calibrated against any independent RC-specific dataset (0.021 appears to be hand-set, not fit).

---

## 2. Trade Dynamics

- **Inputs:** per-edge `C_ij` (capacity), `κ_ij` (cost), `ρ_ij` (political risk) from `network_weights.csv`; seller's `export_fraction`, `food_imperish`; buyer's `caloric_demand()`, current stocks, `capital`; global `price`.
- **Outputs:** stock transfers (`food_imperish`), capital nudges (`gdp`), trade-value accumulators, and (via `_propagate_export_ban`) new export bans on neighbouring nodes.
- **State variables:** `G.edges[...]['active']` (bool, can be deactivated by trigger injection); per-agent `exports_this_step`, `imports_this_step`.
- **Equation (`_gravity_volume`):** `volume = min(export_avail, cap_volume, buyer_deficit×1.2, affordable_kcal)` where `affordable_kcal = (capital / price^1.2) × 1e12`.
- **Parameters:** `G_BASE=6e10` (declared but not actually used in `_gravity_volume` — the function uses `edge_cap` directly from data, not `G_BASE`; a second dead constant, distinct from the RC one above), `PRICE_ELASTICITY=1.2`, `BAN_CONTAGION_RATE=0.30`, `BAN_CONTAGION_CAP=0.80`, `MIN_TRADE_VOLUME=1e6`.
- **External dependencies:** `model.price_system.price` (global, not node-specific — every edge's affordability constraint uses the same single world price); `model.rng` for the political-risk Bernoulli gate.
- **Negative feedback (genuinely stabilizing):** the affordability term — high global price reduces every buyer's `affordable_kcal`, throttling trade volume, which (all else equal) tends to reduce further price pressure from over-purchasing. This is the cleanest stabilizing loop in the model.
- **Positive feedback:** export-ban contagion (`_propagate_export_ban`) — a ban reduces neighbours' effective supply, which lowers their σ, which (via `update_export_policy` next tick) increases their own probability of banning too. Self-reinforcing, but naturally rate-limited (see delay below).
- **Time delays:** contagion-induced bans are overwritten by the node's own `update_export_policy()` at the start of its *next* `agent.step()`, based on its actual σ — so a contagion ban only "sticks" for one tick unless the node's genuine food security independently justifies it. This is a real, useful self-correcting property, not by explicit design comment but by code structure.
- **Saturation:** `BAN_CONTAGION_CAP=0.80` caps contagion probability; `seller.food_imperish × 0.95` safety clamp on any single transfer.
- **Hidden coupling:** every edge references the *same* single global `price` scalar for affordability — there is no node-specific or bilateral price, meaning a price shock anywhere in the world instantly and uniformly affects every importer's purchasing power in the same tick, regardless of that specific bilateral relationship's actual currency/logistics situation. This is a modelling simplification worth flagging for the "sanctions"/"shipping disruptions" future features, which would more naturally act as edge-specific or node-specific cost/capacity modifiers than as global price changes.
- **Assessment:** structurally sound gravity-model design; the affordability negative feedback is a genuine stabilizer. Mathematically stable in isolation. The dead `G_BASE` constant is cosmetic (not a functional bug, but should be removed or wired in for clarity before any publication-grade documentation is generated from this file). Not independently empirically calibrated beyond the ATM (Agricultural Trade Multiplier) correction noted in the file's own comments as partial/blocked pending FAO detailed trade matrix access.

---

## 3. STC Overload Accumulation (FS_index / CC_index / `_detect_overload`)

- **Inputs:** post-trade `agent.food_security` (σ), `agent.sigma_safe_i`, `agent.energy_stress_index`, `agent.climate_modifier`, `agent.technology`, `agent.capital`, `agent.political_risk`, `agent.reserves`, `agent.climate_vuln`.
- **Outputs:** `agent.FS_index`, `agent.CC_index`, `agent.overload_food` (bool), entries appended to `STCEngine.crisis_log`.
- **State variables:** `FS_index` (persists and accumulates tick-over-tick — this is the "slow fuse" of LFBB); `CC_index` (recomputed fresh each tick, not accumulated).
- **Equations:** `FS_index(t) = clip(FS_index(t−1) + stress_push − stress_pull + es_contribution + climate_stress, 0, 2)` where `stress_push = FS_ACCUMULATION_RATE × max(0, 1−σ)`, `stress_pull = FS_DECAY_RATE × max(0, σ−σ_safe)`; `CC_index = clip(0.4749×tech_norm + 0.3002×cap_factor − 0.1066×political_risk + 0.0031×reserve_factor − 0.1152×climate_vuln, 0.05, 1.0)`; overload when `FS_index/CC_index > FOOD_OVERLOAD_RATIO(1.0)`, gated by `t ≥ min_steps_for_overload(1)`.
- **Parameters:** the CC weights above (ML-calibrated per Phase 3, cross-validated R²=0.86); `FS_ACCUMULATION_RATE`, `FS_DECAY_RATE` (hand-set, not independently validated against a real "how fast does food insecurity build" dataset as far as this codebase documents).
- **Positive feedback:** this is the accumulator that RC price amplification (Section 1) feeds back into via the price-ratio term — see Section 1's loop description.
- **Negative feedback:** `stress_pull` term decays FS_index whenever σ recovers above `σ_safe_i` — this exists and is real, but is asymmetric and comparatively weak relative to `stress_push` for structurally low-σ nodes (by construction, `stress_pull` can only ever activate once σ has already recovered past a fairly high bar).
- **Saturation:** **FS_index is clipped to `[0, 2]`, not `[0, 1]`.** This means the FS/CC ratio has no natural ceiling of its own — combined with `CC_index`'s floor of 0.05, the *maximum possible* ratio is 2/0.05 = 40×. This directly explains the very large observed overload ratios (South Asia-other's 6.7–22× range seen across the Phase 2 catalogue) — they are not numerical errors, they are the intended range of this formula, but a 40× theoretical ceiling on a ratio whose *pass* threshold is 1.0 is an extremely wide dynamic range for a binary trigger condition, and is a legitimate candidate for "requires scientific refinement" (Section 11) rather than a bug.
- **Hidden coupling:** `_compute_FS_index()` (in `agent.py`, called both pre- and post-trade) uses `model.price_ratio`, meaning this subsystem is bidirectionally coupled to Section 1's price mechanism — FS_index both *causes* price shocks (via overload count feeding RC amplification) and *is caused by* price (via the price-ratio term). This is the single most consequential loop in the entire causal graph.
- **Assessment:** structurally follows the Homer-Dixon LFBB "slow fuse, big bang" design intent correctly. Empirically calibrated only for CC_index (ML-fit, Phase 3); FS_index's accumulation/decay rates are not independently calibrated. Mathematically capable of runaway (confirmed, Section 1) — the `[0,2]` clip combined with the price-ratio hidden coupling is the specific numerical pathway.

---

## 4. Food Security Evolution (σ)

- **Inputs:** `annual_production` (from Cobb-Douglas, Section 7/9 coupling), `reserves`, `food_imperish`, `_caloric_demand_yr`.
- **Outputs:** `agent.food_security` (σ), `agent.undernourished` (bool).
- **State variables:** none beyond the stocks it reads (σ itself is a derived, not accumulated, quantity — recomputed fresh from current stocks each call).
- **Equation:** `σ = (Q + R_draw + stock_bonus) / D`, where `R_draw = min(reserves, 0.30×D)` and `stock_bonus = min(max(0, food_imperish − θ_imperish×D), 0.50×D)`.
- **Parameters:** the 0.30 and 0.50 caps (hand-set, not independently sourced).
- **External dependencies:** called twice per tick (pre-trade in `agent.step()`, post-trade in `model.step()`'s recompute block) — this is the specific sequencing this session's Phase 2.5 investigation addressed.
- **Positive/negative feedback:** σ itself doesn't self-accumulate, but it is the root input to almost every other subsystem's stress term (Sections 3, 5, 6), making it the single highest-leverage state variable in the model despite being memoryless itself.
- **Saturation:** both `R_draw` and `stock_bonus` are individually capped, but σ overall is *not* clipped — it can exceed any bound (e.g. Pacific/Oceania showed σ=1.092, i.e. 9.2% surplus, in the Phase 2.5 diagnostic) or (implicitly) go arbitrarily low if production and stocks are both near zero.
- **Assessment:** structurally correct, appropriately memoryless (a ratio, not an accumulator) — its risk is entirely inherited from what feeds it (production, reserves) and what reads it (export policy, FS_index), not from any defect in the formula itself.

---

## 5. Coping Capacity (CC_index)

Covered in equation detail under Section 3; treated separately here per your subsystem list, focusing on its own internal structure rather than the overload mechanism it feeds.

- **Inputs:** `technology`, `capital`, `political_risk` (static), `reserves` (via `reserve_factor`), `climate_vuln` (static).
- **State variables:** none of its own — recomputed fresh from current agent attributes every tick (no memory, unlike FS_index).
- **Weights (ML-calibrated, Phase 3):** technology 0.4749 (dominant), capital 0.3002, political risk −0.1066, climate vulnerability −0.1152, reserve adequacy +0.0031 (functionally negligible — confirmed exactly 0.000 contribution for every node at Phase 2.5's step-1 diagnostic).
- **Time delays:** indirect only, via how slowly `technology` and `capital` themselves move (Section 9's capped, logarithmic growth — genuinely slow, multi-step).
- **Saturation:** hard floor 0.05, hard ceiling 1.00.
- **Hidden coupling:** none beyond what's already listed — this is one of the more self-contained subsystems in the model.
- **Assessment:** the only subsystem in this catalogue with genuine, documented, cross-validated empirical calibration (Phase 3's R²=0.86 regression). Structurally sound. The one legitimate concern (already flagged in Phase 3's validation report) is the possible circularity between this regression's target (FAO undernourishment) and other places that same series is used — unresolved, not re-investigated here since it wasn't in this session's scope. The near-zero reserve weight is a genuine calibration finding, not a bug — but it means Section 8 (Reserve Dynamics) is currently a well-built subsystem with almost no causal influence on the rest of the model.

---

## 6. Export-Ban Cascades

Mechanically documented under Section 2 (`_propagate_export_ban`); repeated here with cascade-specific framing.

- **Inputs:** a banning node's outgoing trade edges; each neighbour's own current σ.
- **Outputs:** `neighbour.export_ban = True`, `neighbour.export_fraction = 0.0` (both provisional — see the one-tick self-correction noted in Section 2).
- **Equation:** `P(contagion) = clip(0.30 × max(0, 1−σⱼ), 0, 0.80)`.
- **Positive feedback:** direct — a ban reduces the network's effective supply, and this is the only mechanism in the entire model through which one node's *policy decision* (not a resource shock) directly forces another node's policy, independent of any trigger.
- **Negative feedback / delay:** the next tick's `update_export_policy()` call re-derives `export_ban` purely from that node's own σ, so a contagion-induced ban only persists if independently justified — a real, if implicit, damping mechanism.
- **Hidden coupling:** this is the *only* place `_propagate_export_ban` is called from (`execute_trade_step`, when `seller.export_fraction <= 0`) — meaning export-ban cascades currently only ever originate from a node's own 3-regime export policy (Section 4's σ falling below `SIGMA_WARNING`) or from a trigger directly setting a node's export fraction to 0 (e.g. `2022_ukraine_block`). There is no separate "sanctions" or "war-driven export ban" pathway distinct from this one mechanism — which is good news for the future "sanctions"/"wars" feature list: it means those features can integrate by directly manipulating `agent.export_fraction` / `agent.export_ban` (exactly as `2022_ukraine_block` already does) rather than requiring a new mechanism.
- **Assessment:** structurally sound, appropriately probabilistic (not deterministic contagion, avoiding an unrealistic domino effect), and self-limiting via the one-tick decay property. Not independently calibrated against real 2008/2010/2022 export-ban propagation speed data (the 0.30/0.80 constants appear hand-set).

---

## 7. Energy-Food Coupling

- **Inputs (Arrow 1, energy→food):** `agent.energy_stress_index` (ES), `agent.epsilon_ef` (per-country, Phase 1-documented calibration range 0.18–0.52).
- **Outputs (Arrow 1):** temporarily overwrites `agent.A_i` each tick: `A_i_eff = A_i_base × max(1 − ε_ef×ES, 0.20)`.
- **Inputs (Arrow 2, food→energy):** `agent.food_security` (σ), current energy price `p_energy`.
- **Outputs (Arrow 2):** `agent.xi_biofuel` (land-share state, rate-limited ±0.01–0.02/step), which reduces effective cropland (Section 9) and offsets `ES_index`.
- **State variables:** `EnergyModule._eroi_penalty_global` (monotonically non-decreasing, shared across all nodes); `agent.xi_biofuel` (persists, rate-limited).
- **Equation (ES_index):** `ES = clip(demand_growth + eroi_component + import_risk + climate_stress − renew_offset, 0, 1)`, where **`demand_growth = self._step × 0.018 × fossil_share × 0.40`** — this term is **linear and unbounded in `self._step`**, with no independent cap of its own (only the final `clip(...,0,1)` on the whole ES_index bounds it).
- **Saturation:** Arrow 1's floor at 0.20× (max 80% TFP reduction); Arrow 2's `BIOFUEL_MAX_LAND_SHARE=0.15` cap; ES_index's overall `[0,1]` clip.
- **Positive/negative feedback:** Arrow 2 is a genuine, if modest, negative feedback on ES_index (biofuel substitution reduces energy stress when energy prices are high) — a real stabilizing loop, rate-limited by construction so it can't overshoot quickly.
- **Time delays:** Arrow 2's ±0.01–0.02/step rate limit is an explicit, deliberate lag — a realistic modelling choice (cropland reallocation takes years in reality, not one tick).
- **Hidden coupling — a genuine structural finding:** `climate_stress` is added into **three separate places** from the same underlying `climate_modifier`: (1) directly reduces Cobb-Douglas production via the `C` multiplier (Section 9), (2) adds `0.15×(1−C)` directly into FS_index accumulation (Section 3), and (3) adds `0.10×(1−C)` directly into ES_index (this section). A single climate event is therefore triple-counted across three additive/multiplicative pathways that are not designed to be mutually exclusive. This is not necessarily wrong (real climate shocks *do* affect production, food security, and energy simultaneously) but it means **any future climate-driver feature (drought, rainfall variability, floods) that modifies `climate_modifier` will automatically propagate through all three channels at once** — worth designing deliberately rather than discovering by surprise.
- **Assessment:** Arrow 1 (energy→food) is structurally sound and empirically anchored (per-country ε_ef, Phase 1). Arrow 2 (food→energy) is a well-designed, appropriately rate-limited stabilizer. **The `demand_growth` term is the one clearly identified "capable of unrealistic runaway behaviour" component here** — not a feedback loop in the conventional sense, but a deterministic secular ratchet: ES_index trends toward its ceiling purely as a function of elapsed simulated time, independent of any trigger or real energy-market condition, for every fossil-dependent node. Over a long enough run (a 30+ year policy-optimization horizon, which is explicitly part of the stated future direction) this term alone could dominate energy stress regardless of any policy intervention being tested — a candidate for scientific refinement before Digital Twin / policy-search use.

---

## 8. Reserve Dynamics

- **Inputs:** `food_imperish` (surplus above `θ_imperish×D` feeds replenishment); demand `D` (via `RESERVE_RATIO×food_imperish` target — note: the target is **not** demand-denominated despite the name suggesting a demand-based buffer).
- **Outputs:** `agent.reserves` (accumulates); draws down via `compute_food_security()`'s `R_draw` and via `_consume_food()`'s last-resort draw.
- **Equation:** `target = 0.15 × food_imperish`; `transfer = min(0.05×food_imperish, target − reserves)` per tick (only when `reserves < target`).
- **Saturation:** self-limiting on both ends — asymptotically approaches target from below (5%/step maximum transfer), and consumption draw is capped at 30% of demand per tick in `compute_food_security()`.
- **Positive/negative feedback:** none of concern — this is the most numerically well-behaved subsystem examined in this decomposition, converging smoothly with no runaway pathway identified.
- **Hidden coupling:** the replenishment target is proportional to the node's *own current* imperishable stock, not to its caloric demand or population — meaning a node with chronically low production (and therefore low `food_imperish`) will also have a chronically low reserve *target*, compounding rather than offsetting its structural vulnerability. This is a subtle but real design property: reserves in this model do not function as a demand-anchored strategic buffer (as the real-world "months of import cover" concept implies, and as Phase 1's documentation described it), but as a fraction of whatever stock happens to already exist.
- **Assessment:** mathematically stable, well-behaved, structurally simple. However: (a) as established in Section 5, its calibrated weight in CC_index is functionally negligible (0.0031), so this well-built subsystem currently has almost no influence on system-wide overload dynamics; (b) the target-is-proportional-to-own-stock design (rather than demand-anchored) is a candidate for reconsideration specifically because future "policy optimisation" work will likely want to test reserve-mandate interventions (e.g., "require every node to hold 3 months of demand in reserve" — Phase 2's catalogue already flagged this as the natural lever for exporter-concentration scenarios), and the current target formula would not represent that kind of policy faithfully without modification.

---

## 9. Climate Stress

- **Inputs:** `drought_index`, `heatwave_index`, `flood_index` (per-agent state; near-zero at baseline, set by climate-type trigger injection via `_fire_trigger`).
- **Outputs:** `agent.climate_modifier` ∈ [0.05, 1.0].
- **Equation:** `C = max(0.05, 1 − 0.40×drought − 0.35×heatwave − 0.25×flood)`.
- **State variables:** the three index values themselves — need to be checked for decay-over-time behaviour (not located in this session's review of `agent.py`; worth confirming whether a trigger-injected drought index ever decays back toward zero, or persists until explicitly reset — **flagged as an open question for the next investigation**, not resolved here).
- **Saturation:** hard floor at 0.05 (climate can reduce, but never fully zero, production/coupling terms it feeds).
- **Hidden coupling:** same triple-counting finding as Section 7 (production, FS_index, ES_index all read from the same `climate_modifier`).
- **Assessment:** structurally simple and linear-additive across three named hazard types — a reasonable, extensible starting design for the stated future direction (drought, rainfall variability, floods are literally the three named indices already present, so those specific future features integrate directly and trivially into this existing structure). The main open item is confirming decay/persistence behaviour before building policy-search scenarios that run many simulated years — a short, targeted follow-up, not a large investigation.

---

## 10. Political Instability

- **Inputs:** none, at runtime — this is the key finding for this subsystem.
- **Outputs:** `agent.political_risk` (ρ_i) and edge-level `rho_ij` are used in: CC_index (Section 5, −0.1066 weight), the trade political-risk Bernoulli gate (Section 2), and energy import-risk (Section 7).
- **State variables:** **none that evolve during simulation.** `political_risk` and `rho_ij` are loaded once from `node_parameters.csv`/`network_weights.csv` at initialisation and never updated by any code path found in `agent.py`, `model.py`, `stc_engine.py`, or `trade.py`.
- **The one dynamic hook that exists:** `trade.py::_effective_risk()` accepts a `sanction_penalty` parameter, read from `model.sanction_penalty` (default 0.0), added to the base `rho_ij` and clamped to [0.05, 0.95] — this is a real, if currently unused-by-default, mechanism for a trigger or future feature to raise trade risk on specific edges without touching the underlying calibrated `rho_ij`.
- **Feedback:** none — by construction, political risk in this model is **exogenous and static**, not a variable the simulation's own dynamics can move.
- **Assessment:** this is not a bug — political risk genuinely is one of this model's calibrated *inputs*, not an emergent *output*, and that's a legitimate modelling choice for the current scope. But it is the most important finding for your stated future direction: **"wars" and "sanctions" as future features should be built as trigger-driven, transient modifications to `sanction_penalty` (edge-level) or direct `political_risk`/`export_fraction` overrides (node-level) — exactly mirroring how `2022_ukraine_block` already works — rather than as a new standalone "political instability subsystem."** There is currently no mechanism, and none should be invented in isolation, for the simulation's own trajectory (e.g., a famine) to *cause* rising political instability — if that causal direction is wanted for the Digital Twin, it would need to be added deliberately as a new, explicit feedback (agent unrest → rising `political_risk`), not assumed to already exist.

---

## 11. Cross-Cutting Synthesis — the complete causal graph

```
                    ┌─────────────────────────────────────────────┐
                    │              GLOBAL PRICE (single scalar)     │
                    │         PriceSystem.price, [0.80, 5.00]       │
                    └───────┬───────────────────────────┬──────────┘
                            │ affects buyer               │ read by every
                            │ affordability (§2,          │ agent's FS_index
                            │ NEGATIVE feedback)           │ via price_ratio
                            ▼                              ▼
        ┌───────────────────────────┐         ┌─────────────────────────────┐
        │   TRADE (§2)                │◄────────┤  σ (food security) (§4)      │
        │  gravity model, per-edge    │ export   │  memoryless ratio,           │
        │  C_ij/κ_ij/ρ_ij (STATIC     │ policy   │  root input to almost        │
        │  political risk, §10)       │ (§6)     │  everything below            │
        └──────────┬──────────────────┘         └──────────┬───────────────────┘
                    │ export-ban contagion                    │ feeds
                    │ (POSITIVE, self-limiting,               ▼
                    │  1-tick decay)                ┌─────────────────────────┐
                    ▼                                │  FS_index / CC_index      │
        ┌───────────────────────────┐                │  (§3, §5) — THE central    │
        │  Neighbour σ drops →        │                │  accumulator. FS clip      │
        │  neighbour export policy    │                │  [0,2]; CC clip [0.05,1]   │
        │  (§4/§6 loop)                │                └──────────┬─────────────────┘
        └───────────────────────────┘                              │ overload count
                                                                     ▼
                                                     ┌─────────────────────────────┐
                                                     │  RC PRICE AMPLIFICATION (§1)  │
                                                     │  price_system.shock() ─────┐  │
                                                     │  ★ DOMINANT POSITIVE LOOP ★│  │
                                                     └──────────────┬──────────────┘  │
                                                                    └──────────────────┘
                                                        (feeds straight back to GLOBAL PRICE)

        ┌───────────────────────────┐         ┌─────────────────────────────┐
        │  ENERGY (§7)                 │◄───────►│  CLIMATE (§9)                 │
        │  ES_index (UNBOUNDED         │  both   │  drought/heat/flood →         │
        │  demand_growth term —        │  feed   │  climate_modifier →           │
        │  secular ratchet, not a      │  triple-│  triple-counted into          │
        │  feedback loop)              │  count  │  production + FS + ES          │
        └──────────────┬────────────────┘  (§7/§9)└─────────────────────────────┘
                        │ Arrow 1: reduces A_i (production, §9)
                        │ Arrow 2: biofuel land share (rate-limited,
                        │   genuine NEGATIVE feedback)
                        ▼
        ┌───────────────────────────┐
        │  PRODUCTION (Cobb-Douglas)   │
        │  §9 — feeds σ (§4) directly   │
        └───────────────────────────┘

        ┌───────────────────────────┐
        │  RESERVES (§8)                │  well-behaved, self-limiting,
        │  target ∝ own food_imperish   │  but CC_index weight ≈ 0 →
        │  (not demand-anchored)        │  currently near-zero systemic
        └───────────────────────────┘  influence
```

**The one loop that matters most:** `overload count → RC price shock →
global price → every node's FS_index (via price_ratio) → overload count`.
Every other subsystem in this graph is either a tributary into that loop
(trade, export bans, energy, climate) or downstream of it (production,
reserves, coping capacity as a modifier of how fast a node enters the
loop). This is why the Phase 2.5 sequencing fix — which changed *when*
overload count is measured relative to trade — had such an outsized effect
on long-horizon validation: it didn't just fix a timing artefact, it
changed the input timing to the model's single dominant feedback loop.

---

## 12. Verdict table

| Subsystem | Structurally correct | Empirically calibrated | Mathematically stable | Runaway-capable |
|---|---|---|---|---|
| RC price amplification | Partially (contagion half is dead code) | No (hand-set constant) | No | **Yes — primary source** |
| Trade dynamics | Yes | Partially (ATM correction incomplete) | Yes | No |
| STC overload accumulation | Yes | Partially (CC yes, FS rates no) | Conditionally (depends on §1) | Yes, via §1 coupling |
| Food security evolution (σ) | Yes | N/A (pure ratio) | Yes | No |
| Coping capacity | Yes | **Yes** (only fully-validated subsystem) | Yes | No |
| Export-ban cascades | Yes | No | Yes (self-limiting) | No |
| Energy-food coupling | Arrow 1 yes; Arrow 2 yes | Arrow 1 yes (per-country ε_ef); Arrow 2 no | No — `demand_growth` term is an unbounded secular ratchet | Yes — but as a trend, not a feedback loop |
| Reserve dynamics | Yes, but target formula misrepresents "strategic reserve" concept | No | Yes | No |
| Climate stress | Yes (simple, extensible) | Unknown (decay/persistence not confirmed this session) | Likely yes, unconfirmed | No |
| Political instability | Yes, as a static input (not a bug) | Yes (it's just data) | N/A (no dynamics) | No |

---

## 13. Which mechanisms require scientific refinement (not numerical tuning) before Digital Twin / policy-optimisation work

1. **RC price amplification's missing negative feedback** — needs a designed counteracting term (e.g., a genuine decay of cascade intensity, or a supply-response term), not a smaller constant. Also: decide whether to wire up the currently-dead contagion-boost pathway or remove it — leaving inert code that the model's own documentation describes as active is a reproducibility hazard for anyone reading `EQUATIONS.md` without also reading the source.
2. **FS_index's `[0,2]` saturation ceiling** relative to a `>1.0` trigger threshold gives a 40× dynamic range on a binary condition — worth a deliberate redesign (e.g., a smoother severity-weighted overload measure) rather than a binary flag with this much headroom above its own trigger point.
3. **Energy `demand_growth`'s unbounded step-linear term** — needs an explicit saturating form (e.g., logistic in elapsed time, or reset/rebased periodically) before any multi-decade policy-search run, or every long-horizon experiment will trend toward energy overload regardless of policy quality.
4. **Reserve target formula** (proportional to own stock, not to demand) — needs redefining as demand-anchored before it can faithfully represent reserve-mandate policy interventions, which the stated future direction explicitly wants to test.
5. **Climate/production/FS/ES triple-counting** — not necessarily wrong, but needs a deliberate design decision (documented, not incidental) before adding the new climate drivers (rainfall variability, floods as a *distinct* mechanism from the existing flood_index) so the counting stays intentional as complexity grows.

## 14. How future features should integrate (per your explicit instruction)

- **Wars / sanctions:** hook into `sanction_penalty` (edge-level, already exists) and direct `export_fraction`/`political_risk` overrides (node-level, already exists via the trigger mechanism) — do not build a new "conflict subsystem."
- **Fertilizer shortages / phosphorus scarcity:** per this session's B3 counterfactual finding, there is no live fertilizer state variable — route through the energy-food coupling (§7, Arrow 1) as this session's `triggers_china_fertilizer_ban` already does, or make the routing explicit and permanent rather than trigger-only if this becomes a recurring policy lever.
- **Fuel crises / shipping disruptions:** fuel crises route naturally through §7 (energy_shock); shipping disruptions have no dedicated mechanism yet — the closest existing hook is `seller.logistics_disruption`/`buyer.logistics_disruption` in `trade.py`'s `_gravity_volume`, already present but not yet exposed as a first-class trigger type.
- **Drought / rainfall variability / floods:** already directly supported by §9's three named indices — no new subsystem needed, only new trigger configurations (exactly as this session's new historical/counterfactual triggers already demonstrate).
- **Node-level and global policy optimisation:** the natural intervention points, given this graph, are `export_fraction` caps (§6), `RESERVE_RATIO`/reserve targets (§8, pending the redefinition in Section 13), and `sanction_penalty` (§10) — these are the levers already wired into the causal graph; an optimiser should search over these rather than inventing new state variables.

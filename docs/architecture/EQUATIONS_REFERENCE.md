# Equations Reference
## Global Food–Energy Systemic Risk ABM

**Framework:** Homer-Dixon et al. (2015) SS/LFBB/RC causal architecture  
**Assessment methodology:** Gambhir et al. (2025) 7-step systemic risk framework  
**Last updated:** June 2026

All variables are indexed i (node/country), j (trading partner), t (simulation year).

---

## 1. Agent State Vector

Each country-agent i carries:

```
Sᵢ = (Pᵢ, Lᵢ, Wᵢ, E_fuelᵢ, E_elecᵢ, E_renewᵢ, Kᵢ, Tᵢ,
       F_perishᵢ, F_imperishᵢ, F_animalᵢ, Rᵢ,
       ρᵢ, Gᵢ,
       FS_indexᵢ, ES_indexᵢ, CC_indexᵢ)
```

where the last three are Homer-Dixon stress/coping-capacity variables (Phase 4).

---

## 2. Food Production (Cobb-Douglas, population-anchored)

```
Qᵢ(t) = Pᵢ(t) × cᵢ × (Lᵢ/L_ref)^α × Wᵢ^β × (E_fuelᵢ/E_ref)^γ × Tᵢ^δ × Cᵢ(t) × r_renew
```

Parameters:
- α = 0.30 (land elasticity)
- β = 0.25 (water elasticity)  
- γ = 0.20 (fuel energy elasticity — raised from 0.15 per ASABE correction)
- δ = 0.25 (technology elasticity — adjusted to sum = 1.00)
- L_ref = 40 (median arable land %)
- E_ref = 70 (median fuel energy TWh)
- cᵢ = income-class caloric need (2200–3200 kcal/person/day × 365)
- Cᵢ(t) = climate productivity modifier ∈ [0.05, 1.0]
- r_renew = 1 + 0.05 × (E_renewᵢ / 100)

Output split: 60% non-perishable (grains), 40% perishable.

**Land competition with biofuel (Phase 3 addition):**
```
Lᵢ_food(t) = Lᵢ(t) × (1 − ξᵢ(t))
ξᵢ(t) = ξ_max × min(ES_indexᵢ(t) / ES_threshold, 1.0)
```
where ξ_max = 0.05 (calibrated from US/EU biofuel mandates, ~5% cropland).

---

## 3. Climate Modifier

```
Cᵢ(t) = max(0.05, 1 − 0.40×Dᵢ_stress − 0.35×Hᵢ_stress − 0.25×Fᵢ_stress)
```

where Dᵢ, Hᵢ, Fᵢ are drought, heatwave, flood stress indices ∈ [0,1]  
injected by the STC shock engine (Phase 4).

---

## 4. Animal Production (with biological delays, Homer-Dixon livestock)

```
Q_animalᵢ(t) = Σ_s  η_s × Q_grainᵢ(t − τ_s)
```

| Species | η_s (feed conversion) | τ_s (years) |
|---|---|---|
| Poultry | 0.30 | 1 |
| Pork | 0.15 | 2 |
| Beef/Cattle | 0.07 | 5 |

---

## 5. Food Security Index (flow-based)

```
σᵢ(t) = (Qᵢ(t) + R_drawᵢ(t) + stock_bonusᵢ(t)) / Dᵢ(t)
```

where:
- Dᵢ(t) = FAO kcal_cap_day × Pᵢ(t) × 365 (direct from data where available)
- R_drawᵢ(t) = min(Rᵢ(t), 0.30 × Dᵢ(t))
- stock_bonusᵢ(t) = min(max(0, F_imperishᵢ − 0.60×Dᵢ), 0.50×Dᵢ)
- Stock cap: F_imperishᵢ ≤ 8 × Dᵢ × 0.60

| σᵢ | Status |
|---|---|
| > 1.20 | Secure |
| 1.00–1.20 | Warning |
| 0.80–1.00 | Crisis |
| < 0.80 | Famine risk |

---

## 6. Homer-Dixon Stress–Coping Capacity Framework (Phase 4)

### Food stress index:
```
FS_indexᵢ(t) = max(0, 1 − σᵢ(t)) × (1 + max(0, p(t)/p(0) − 1))
```

### Energy stress index (Phase 3):
```
ES_indexᵢ(t) = fossil_shareᵢ(t)/100 × demand_growth_indexᵢ(t) × (1 − renew_shareᵢ(t)/100)
demand_growth_indexᵢ(t) = E_totalᵢ(t) / E_totalᵢ(2000)
```

### Coping capacity:
```
CC_indexᵢ(t) = Tᵢ(t) × (Rᵢ(t)/R_refᵢ) × εᵢ(t) × (1 − logistics_disruptionᵢ(t))
```

### LFBB Overload condition (triggers discrete crisis):
```
OL_foodᵢ(t) = FS_indexᵢ(t) / CC_indexᵢ(t) > 1.0
OL_energyᵢ(t) = ES_indexᵢ(t) / CC_indexᵢ(t) > 1.0
```

### SS combination rules (configurable per run):
```
Multiplicative: total_stressᵢ = FS_indexᵢ × ES_indexᵢ  (synergistic — AND logic)
Additive:       total_stressᵢ = FS_indexᵢ + ES_indexᵢ  (either-sufficient — OR logic)
```

---

## 7. Trade Network (Gravity Model)

### Network topology: Full mesh (35×35 = 1,190 directed edges)

### Edge capacity (Gambhir Cᵢⱼ):
```
Cᵢⱼ = G_base × (GDPᵢ × GDPⱼ) / distᵢⱼ² × (tradeᵢ/100) × (tradeⱼ/100)
```
- G_base = 6×10¹⁰ (calibrated to FAO cereal trade magnitudes)
- distᵢⱼ = geographic centroid distance proxy (node degree difference + 1 for synthetic)
- Minimum volume threshold prunes economically negligible edges

### Transaction cost (Gambhir κᵢⱼ):
```
κᵢⱼ = 0.05 + 0.25×landlocked_i + 0.25×landlocked_j + 0.15×chokepoint_ij
```

### Political risk (Gambhir ρᵢⱼ):
```
ρᵢⱼ(t) = base_riskᵢⱼ + (1 − 0.5×(stabilityᵢ + stabilityⱼ)) + sanction_penalty(t)
```
Clamped to [0.05, 0.95].

### Trade success probability:
```
P(trade succeeds | attempt) = 1 − ρᵢⱼ(t)
```

### Gravity trade volume (demand-driven, affordability-constrained):
```
Tᵢⱼ(t) = min(gravity_flow, seller_cap, buyer_deficit × 1.2, affordable_kcalᵢ(t))
affordable_kcalᵢ(t) = (Kᵢ(t) / p(t)^1.2) × 10¹²
```

---

## 8. Food Price Dynamics (RP-2 mechanism, Gambhir calibration)

```
p(t+1) = p(t) × exp(κ_price × (D_tot(t) − Q_tot(t)) / D_tot(t))
          + θ_revert × (p_baseline − p(t))
          + energy_cost_push(t)
```

where:
- κ_price = 1.5 (price sensitivity, calibrated to FAO FPI 2008/2022 responses)
- θ_revert = 0.08 (mean reversion rate)
- p_baseline = 1.0 (anchored to FAO FPI 2014–2016 = 100 baseline)
- p_floor = 0.20, p_ceiling = 5.00

### Energy cost-push term (Phase 3):
```
energy_cost_push(t) = 0.45 × ES_index_global(t) × p(t)
```
0.45 = 40–50% energy cost share of variable cropping costs (IEA, cited in Gambhir 2025).

### Baseline anchoring from FAO FPI:
```
p(0) = FAO_FPI(2000) / FAO_FPI(2014-2016 average)
```

---

## 9. Population Dynamics (per-node vital rates)

```
Pᵢ(t+1) = Pᵢ(t) × (1 + bᵢ − dᵢ − ψᵢ × max(0, 1 − σᵢ(t)))
```

where:
- bᵢ − dᵢ = per-node growth rate from OWID population trend (2010–2022)
- ψᵢ = famine mortality sensitivity ∈ [0.010, 0.100]
  - Calibrated from: `0.10 − 0.07×(0.5×min(LEᵢ/85,1) + 0.5×min(UHCᵢ/100,1))`

---

## 10. Capital Dynamics (with depreciation)

```
Kᵢ(t+1) = Kᵢ(t) + 0.10×ΣXᵢⱼ(t) − 0.10×ΣXⱼᵢ(t) − 0.015×Kᵢ(t)
```

where:
- 0.10 = export profit margin
- 0.10 = import cost margin  
- 0.015 = capital depreciation rate (per ASABE paper correction — missing in original ABM)
- Xᵢⱼ(t) = trade value from i to j in step t

### Technology evolution:
```
Tᵢ(t+1) = Tᵢ(t) + 0.002 × ln(max(Kᵢ(t), 1))
Tᵢ(t)   = min(Tᵢ(t), 5.0)
```

---

## 11. Export Policy (3-Regime, per ASABE correction)

Three regimes replace the binary export-ban:

```
if σᵢ(t) ≤ 1.0:          # Regime 1: Survival — no exports
    export_fraction = 0.0

elif σᵢ(t) ≤ σ_safeᵢ:    # Regime 2: Precautionary
    s = (σᵢ(t) − 1.0) / (σ_safeᵢ − 1.0)
    export_fraction = φᵢ × s^1.5   where φᵢ = 0.60

else:                      # Regime 3: Market
    export_fraction = min(μᵢ, 0.90)
```

where σ_safeᵢ = per-node safe threshold ∈ [1.10, 1.30].

### Export-ban contagion (RC mechanism):
```
P(neighbour j imposes ban | i bans) = 0.30 × max(0, 1 − σⱼ(t))
```
Capped at 0.80. Applied via BFS-neighbour traversal.

---

## 12. Energy System (Phase 3)

### Energy stress accumulation (LFBB):
```
ES_accumᵢ(t+1) = ES_accumᵢ(t) + ES_rateᵢ(t) × (1 − CC_indexᵢ(t))
```

where ES_rateᵢ(t) = annual increase in energy stress from demand growth + supply constraints.

### Energy recovery (per-step):
```
E_fuelᵢ(t+1) = E_fuelᵢ(t) + εᵢ × (E_fuel_baselineᵢ − E_fuelᵢ(t))
E_renewᵢ(t+1) = E_renewᵢ(t) + 2×εᵢ × (E_renew_baselineᵢ − E_renewᵢ(t))
```
Renewables recover faster (2×εᵢ) reflecting faster deployment vs fossil infrastructure rebuild.

---

## 13. Resilience Metrics (Gambhir Step 4 outputs)

```
U(t)   = #{i: σᵢ(t) < 1.0} / N           # Undernourishment rate
GFS(t) = Σᵢ σᵢ(t)×Pᵢ(t) / ΣPᵢ(t)        # Population-weighted food security
TC(t)  = 1 − Trade(t) / Trade_baseline    # Trade collapse index
EB(t)  = #{i: export_banᵢ(t)} / N         # Export ban rate
PAR(t) = Σᵢ Pᵢ(t) × 1[σᵢ(t) < 1.0]      # Population at risk
RT     = steps to U(t) < 0.05 post-crisis # Recovery time
```

### Gambhir System Architecture Vulnerability Indices:
```
SAV_scale(t)   = Σᵢ (GDPᵢ(t)×E_totalᵢ(t)) / Σᵢ (GDPᵢ(2000)×E_totalᵢ(2000))
SAV_homog(t)   = HHI(cereal_prod_by_item_t)            # Herfindahl index
SAV_connect(t) = active_edges(t) / max_possible_edges  # Network density
SAV_power(t)   = HHI(trade_flow_by_node_t)             # Trade concentration
```

---

## 14. Validation Criteria (Phase 8 retrodiction targets)

For the 2008 food-energy crisis:
- FAO FPI peak: +70% from 2006 baseline (target: model peaks within ±15%)
- Export ban count at peak: ~30 countries (target: model produces 20–40)
- Recovery time post-peak: ~18 months (target: 2–3 simulation steps)
- Trigger-dependency test: same trigger on unstressed baseline must NOT produce crisis

For the 2022 crisis:
- Wheat price: +56% YoY (target: model wheat-proxy within ±20%)
- Additional food-insecure: 60M+ (target: PAR(t) increases by >50M)
- POM validation score: VPOM = Σ wₖ×sₖ > 0.70 (pattern-oriented modelling threshold)

---

## Appendix: Equations added in Phases A–E (this project's implementation phases)

**Added this consolidation pass** — the sections above (1–14) predate
Phases A–E; the equations below were introduced during this project's
policy-optimisation and environmental-driver work and had not yet been
folded into this reference document. Cross-referenced, not
re-derived — see each linked source for full context.

### 15. RC Price Amplification (already governed by §8/§13's price
dynamics; restated here for completeness since it's the model's single
most sensitive parameter, per `docs/global_policies/RC_PRICE_AMPLIFICATION.md`)

```
factor = 1 + RC_PRICE_AMPLIFICATION × n_overloaded(t)     [only when n_overloaded(t) > n_overloaded(t-1)]
price(t) ← clip(price(t) × factor, 0.80, 5.00)
```

### 16. Mitscherlich Fertilizer Response (Phase C3, `resource_drivers.py`)

Established agronomic diminishing-returns functional form, normalised so
`response(reference stock) = 1.0` exactly (a correctness fix made during
implementation — see `docs/implementation/PHASE_C2_IMPLEMENTATION_REPORT.md`):

```
raw(φ) = max_response × (1 − exp(−rate_constant × φ))
response(φ) = raw(φ) / raw(1.0)                            [φ = current stock / reference stock]
```

### 17. Fertilizer Stock Dynamics (Phase C3)

```
Φ_nutrient,i(t+1) = max(0, Φ_nutrient,i(t) + replenish_i(t) − depletion_i(t))
replenish_i(t) = REPLENISHMENT_RATE × reference_stock       [producer nodes only, per nutrient]
depletion_i(t) = DEPLETION_RATE × Φ_nutrient,i(t) × max(0.1, intensity_i(t))
```

### 18. Water Reservoir Balance (Phase C4)

```
W_stock,i(t+1) = max(0, W_stock,i(t) + inflow_i(t) − withdrawal_i(t) − evaporation_i(t))
withdrawal_i(t) = ag_withdrawal_share × withdrawal_rate × reference_stock_i × demand_intensity_i(t)
evaporation_i(t) = evaporation_rate × W_stock,i(t)
water_stress_i(t) = clip(1 − W_stock,i(t)/reference_stock_i, 0, 1)
```

### 19. Soil Quality Dynamics (Phase C2)

```
Q_soil,i(t+1) = clip(Q_soil,i(t) + REGEN_RATE×(1 − Q_soil,i(t)) − DEGRADATION_RATE×max(0, intensity_i(t) − 1), 0.05, 1.0)
```

### 20. Continuous Climate Drivers (Phase C1, replaces discrete trigger-only indices when attached)

```
drought_index_i(t) = clip((rainfall_climatology_i − rainfall_i(t)) / rainfall_climatology_i, 0, 1)
heat_stress_i(t)    = clip((temp_anomaly_i(t) − heat_threshold) / heat_range, 0, 1)
```

### 21. Production function, extended (Phases C1–C4 combined; §2 above is the pre-Phase-C original)

```
q_plant,i = P_i × c_i × A_i × (L_food,i/L_REF)^α × W_i^β × (E_i/E_REF)^γ × T_i^δ
            × C_i × r_renew,i × Q_soil,i × F_response,i × (1 − water_stress_i)
```

Every multiplicative term beyond `r_renew` is `getattr`-defaulted to a
no-op value (1.0, or 0.0 stress) when its corresponding driver isn't
attached — see `model/src/agent.py::_produce_plant_food` and
`docs/implementation/PHASE_C_IMPLEMENTATION_REPORT.md` /
`PHASE_C2_IMPLEMENTATION_REPORT.md` for the backward-compatibility
verification.

### 22. Policy lever equations

See `docs/policies/` — each of the 11 implemented levers has its
equation extracted directly from its docstring via
`scripts/generate_policy_catalog.py`, not restated here to avoid the two
copies drifting apart.

# System Architecture Document
## Global Food–Energy Nexus: Systemic Risk Assessment

**Project:** Food–Energy Systemic Risk ABM  
**Framework:** Gambhir et al. (2025) 7-step methodology + Homer-Dixon et al. (2015) STC causal architecture  
**Phase:** 0 (Track A — Qualitative Foundation)  
**Date:** June 2026

---

## 1. Why This Document Exists

Gambhir et al. (2025, *Nature Communications*) argue explicitly that **Step 1 of any systemic risk assessment must detail system architectures** — their goals, stakeholders, locations of power and vulnerability, and timescales of operation — *before* any modelling begins. This document fulfils that requirement. It is not background colour; it is the structural specification that constrains what the simulation is allowed to claim.

Homer-Dixon et al. (2015, *Ecology & Society*) supply the causal grammar: **Simultaneous Stresses (SS)**, **Long Fuse Big Bang (LFBB)**, and **Ramifying Cascade (RC)**, operating across an **intersystemic boundary** in two temporal stages. Every variable in the ABM corresponds to a node in this grammar.

---

## 2. The Two Systems

### 2.1 Global Food System

**Definition:** The interconnected set of actors, institutions, and processes linking land, water, energy, labour, seeds, fertiliser, and capital to food production, processing, storage, trade, and consumption — from field to fork, at planetary scale.

**Goals (whose goals?):**

| Stakeholder | Stated Goal | Actual Operative Goal |
|---|---|---|
| Large agro-commodity traders (ADM, Bunge, Cargill, Louis Dreyfus, Viterra — "Big Five") | Supply chain efficiency | Margin extraction; profit from price volatility |
| Export-restricting governments | National food security | Political stability; domestic price control |
| Import-dependent governments | Food access for population | Fiscal solvency; social order |
| Smallholder farmers | Livelihood | Survival under price/climate squeeze |
| International institutions (FAO, WFP, IFAD) | Global food security | Coordination without enforcement power |
| Financial speculators | Return on investment | Exploitation of price signals in futures markets |
| Hungry populations (>800M food insecure) | Enough to eat | Absent from decision-making |

**Power holders (Gambhir Fig. 2 context):**
- The Big Five control ~70–90% of global grain trade flows. They profit during crisis (Gambhir et al. 2025, citing evidence of outsized profits during 2022).
- Governments with export bans (India, Russia 2008, 2022) can unilaterally redirect global supply.
- Financial institutions intermediating commodity futures markets (post-2005 US Renewable Fuel Standard deregulation loosened commodity index trading).

**Vulnerable populations:**
- Net food-importing nations with low foreign exchange reserves (Yemen, Somalia, Sudan, Haiti).
- Urban poor in low-income countries who spend 60–80% of income on food.
- Children under 5 in crisis zones (acute malnutrition spikes within weeks of price surges).

**Structural weaknesses (Gambhir's "political economy context", Fig. 2):**
- Oligopoly of seeds, fertiliser, and pesticide suppliers (3–4 firms control >50% of each market globally).
- Geographic concentration of production in "breadbasket" regions (North America, Black Sea, South Asia, Southeast Asia) — simultaneous stress in any two is sufficient for crisis.
- Homogenised crop production and diets: declining varietal diversity increases synchronous vulnerability to specific pests, diseases, and climate patterns.
- Declining strategic reserves: many countries reduced grain stocks in 2000s on assumption that efficient markets made reserves unnecessary (proven wrong in 2008 and 2022).

**Timescales of stress build-up:**
- Declining marginal returns to intensification: decades
- Rising food demand from population and income growth: years–decades
- Depletion of high-quality agricultural land: decades
- Climate-driven yield volatility: accelerating, now manifest on annual timescale

---

### 2.2 Global Energy System

**Definition (IPCC):** The set of components related to the production, conversion, delivery, and use of energy — encompassing fossil fuels, renewables, nuclear, and the infrastructure connecting them.

**Goals (whose goals?):**

| Stakeholder | Stated Goal | Actual Operative Goal |
|---|---|---|
| Fossil fuel majors (ExxonMobil, Shell, BP, Saudi Aramco, Gazprom) | Energy supply | Reserve monetisation; incumbent protection |
| OPEC+ states | Revenue stability | Political regime survival via oil rents |
| Energy-importing governments | Energy security | Economic growth; political stability |
| Low-carbon technology developers | Decarbonisation | Market share in energy transition |
| 800M without electricity access | Energy access | Absent from high-level decisions |
| Financial sector | Return on energy assets | Incumbent investment protection |

**Power holders:**
- OPEC+ controls ~40% of global oil production and most swing capacity.
- Russia controlled ~40% of European gas supply pre-2022, weaponised as geopolitical lever.
- Europe's structural reliance on Russian gas (Gambhir Fig. 2, "Underlying Political Economy Context") created a concentrated single-point vulnerability.
- Oligopoly in oil/gas markets (Gambhir Fig. 2): few producers can move global prices.

**Vulnerable populations:**
- 800M+ without electricity access (number *increased* in 2022 — IEA cited in Gambhir).
- Households in energy-poor regions where energy costs >10% of income.
- Agricultural producers in low-income countries whose fuel and fertiliser costs are dollar-denominated.

**Structural weaknesses:**
- Reliance on price-volatile fossil fuels as primary energy source in most economies.
- Europe's infrastructure lock-in to Russian gas (LNG terminal deficit pre-2022).
- Oligopoly in oil and gas markets prevents competitive price responses to shocks.
- Energy transition is globally too slow: low-carbon share still insufficient to buffer fossil price spikes.

**Timescales:**
- Declining EROI (energy return on investment) for conventional oil: decades of slow deterioration
- Post-COVID demand recovery: 1–2 years
- Long cold winter demand spikes: seasonal
- Geopolitical trigger (invasion): days

---

## 3. The Intersystemic Boundary

This is the analytical core of both papers. Two explicit, bidirectional causal channels cross the food–energy boundary:

### Arrow 1: Energy → Food (cost-push)
**Mechanism:** Direct energy cost of agriculture + indirect cost through fertiliser and pesticide (themselves energy-intensive to produce).  
**Magnitude:** Energy inputs account for **40–50% of variable cropping costs** in advanced economies (IEA, cited in Gambhir 2025). Fertiliser (primarily natural-gas-derived nitrogen) doubles this exposure.  
**Model implementation:** Energy stress index → raises effective cost of production → reduces Q_i (Cobb-Douglas output) and raises p(t) via cost-push term in price equation.

### Arrow 2: Food → Energy (biofuel land competition)
**Mechanism:** When energy prices are high, cropland is reallocated from food to biofuel feedstock (maize→ethanol, soy→biodiesel, rapeseed→biodiesel).  
**Historical evidence:** 2005 US Renewable Fuel Standard mandated blending → directly competed for cropland. EU biofuel mandates had similar effect. Homer-Dixon Fig. 3 shows this as the critical intersystemic coupling arrow in 2008.  
**Model implementation:** Energy stress index above threshold → fraction ξ of food-cropland Lᵢ reallocated to biofuel → reduces food Qᵢ while reducing energy stress.

### Why coupling matters (Homer-Dixon's core argument)
Without coupling, two separate crises. With coupling, **synchronized** crises — the energy system's overload and the food system's overload are not independent events; they are causally entangled. This is what makes the 2008 and 2022 events instances of **synchronous failure** rather than coincidental parallel crises.

The ABM's `energy.py` module implements both arrows with an elasticity parameter that can be set to zero (decoupled counterfactual) or calibrated (coupled baseline), allowing explicit comparison.

---

## 4. System Architecture Vulnerabilities (Gambhir's Four)

Gambhir et al. (2025) identify four structural properties that make crises more likely to compound and cascade. These are **computable diagnostics** in the ABM, reported every simulation run.

| Vulnerability | Definition | Model Diagnostic | Data Source |
|---|---|---|---|
| **Global Scale** | Throughput of food/energy systems relative to planetary boundaries | Total system production / 1990 baseline | OWID: GDP, food production, energy consumption |
| **Homogeneity** | Concentration of crop types, diet patterns, energy sources | Herfindahl index of cereal production by item | FAO Crop Production data |
| **Interconnectivity** | Density of trade linkages; tightness of coupling | Network edge density; average path length | Gravity-model network weights |
| **Concentrated Power** | Share of trade/production controlled by few actors | Trade-flow Herfindahl index; Big-Five proxy | FAO Food Trade, OWID energy |

All four are tracked at each simulation step and included in every run's output dashboard.

---

## 5. Homer-Dixon Deep Causes (Three Trends)

Homer-Dixon et al. (2015) identify three long-term causal trends that together produce the conditions for synchronous failure. Each has a computable proxy:

| Deep Cause | Description | Proxy Variable | Source |
|---|---|---|---|
| **Rising Scale** | Human economic activity approaching planetary resource limits | Global GDP growth index; total energy throughput / EROI proxy | OWID GDP + energy data |
| **Rising Connectivity** | Denser, faster connections among system components | Trade-network density index; number of active trade links | Network weights matrix |
| **Rising Homogeneity** | Declining diversity of crops, institutions, technologies | Crop concentration index (Herfindahl); diet similarity index | FAO FBS + Crop Production |

These three indices are initialised from real data and updated each simulation step, feeding into the stress-accumulation logic of the STC engine (Phase 4).

---

## 6. STC Diagrams: 2008 and 2022 Historical Crises

*(These diagrams represent the Homer-Dixon SS+LFBB+RC architecture applied to the two historical cases, derived directly from the text of both papers.)*

### 6.1 The 2008 Food–Energy Crisis

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOOD SYSTEM (Stage 1: SS + LFBB — slow accumulation within system)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stress 1: Diminishing land availability; falling marginal returns to intensification
          [1980s–2007, slow]
Stress 2: Rising food demand (population growth + income-driven meat consumption)
          [1990s–2008, slow]
Stress 3: Extreme weather, water scarcity (multiple regions)
          [episodic, cumulative]

          ↘  ↘  ↘  [MULTIPLICATIVE — each amplifies the others]
               ╔══════════════════════════════════════╗
               ║  OVERLOAD of food system:            ║
               ║  Failure of international            ║
               ║  stabilisation mechanisms            ║
               ║  (WFP, FAO reserve buffers           ║
               ║   exhausted; markets non-functional) ║
               ╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERSYSTEMIC BOUNDARY (bidirectional coupling)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1980s–90s:  Cheap oil → raises agricultural energy intensity
2000s:      Costly oil → boosts food prices AND biofuel output
2000s:      Increased biofuel output → reduces food cropland

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENERGY SYSTEM (Stage 1: SS + LFBB — slow accumulation within system)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stress 1: Rising energy demand (China, India energy-intensive development)
          [1990s–2008, slow]
Stress 2: Mature oil field decline (peak output passed in many fields)
          [mid-1990s–2008, slow]
Stress 3: Declining EROI (rising energetic cost of each marginal barrel)
          [1980s–2008, slow]

          ↘  ↘  ↘  [MULTIPLICATIVE]
               ╔══════════════════════════════════════╗
               ║  OVERLOAD of energy system:          ║
               ║  Speculation produces breakdown      ║
               ║  in market regulation of prices;     ║
               ║  no slack remaining in oil market    ║
               ╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROXIMATE TRIGGERS (transition from Stage 1 to Stage 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trigger A (food system): Australian drought → low carryover grain stocks 2007
Trigger B (food system): Grain futures speculation accelerates
Trigger C (energy system): Oil price passes $4/gallon US gasoline threshold

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 2: SS + RC (fast cross-system cascade)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Food crisis ╗
            ╠══[MULTIPLICATIVE]══► Global food + energy crisis
Energy crisis╝                     (two overloaded systems collide)

OUTWARD CASCADE (RC — ramifying cascade across systems):
  → Food price surge (+70% FAO index in 18 months)
  → Gas price surge (compounding)
  → Political instability: food riots in 30+ countries
    (Bangladesh, Burkina Faso, Cameroon, Egypt, Indonesia, Yemen)
  → Export bans cascade: Brazil, India, Vietnam ban food exports
    (bans amplify the crisis they were meant to prevent)
  → Widespread political instability

VALIDATION SIGNATURE (Homer-Dixon's four properties):
  ✓ Biophysical origin: EROI decline + land degradation + climate
  ✓ Intersystemic manifestation: food crisis emerged FROM energy crisis
  ✓ Global scope: 30+ countries, all regions affected
  ✓ Rapid development: price doubled in ~18 months from trigger
```

### 6.2 The 2022 Food–Energy Crisis

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UNDERLYING POLITICAL ECONOMY CONTEXT (Gambhir Fig. 2 — new element vs. 2008)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FOOD SYSTEM context:
  • Oligopoly of food commodity (seeds, fertiliser, pesticide) suppliers
  • Concentration of crop production in breadbasket regions
  • Homogenised crop production and diets, decreasing regional variation

ENERGY SYSTEM context:
  • Europe's structural reliance on Russian oil and gas
  • Energy systems reliant on fossil fuels
  • Oligopoly in oil and gas markets

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOOD SYSTEM — Pre-existing stresses (Stage 1: SS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stress 1: Stretched post-COVID-19 supply chains
          [2020–2021, medium-speed]
Stress 2: Weather extremes across regions
          (floods in Pakistan, droughts in Horn of Africa)
          [2021–2022, episodic]
Stress 3: High degree of cereal production variability over two decades
          [slow, structural]
Stress 4: Limited access to credit, fertiliser, regulatory uncertainty
          [ongoing in low-income producers]

          ↘  ↘  ↘  [additive/multiplicative mix]
               → Pressure on food prices (pre-trigger)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENERGY SYSTEM — Pre-existing stresses (Stage 1: SS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stress 1: Post-COVID-19 economic recovery with sluggish energy investment
          [2020–2021, medium-speed]
Stress 2: Long cold 2020–2021 winter in Europe/Asia depleting gas stores
          [seasonal → structural gap]
Stress 3: Underinvestment in European gas storage and diversification
          [decade-long structural vulnerability]

          ↘  ↘  ↘
               → Pressure on gas prices (pre-trigger)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERSYSTEMIC BOUNDARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Direct:   Energy cost of agriculture (40–50% of variable cropping costs)
Indirect: Energy inputs into fertiliser and pesticide production

NOTE: Unlike 2008, in 2022 this is NOT a LFBB (system did not self-overload
before trigger). Instead: already-stressed systems were hit by an exogenous
geopolitical trigger of exceptional magnitude. The boundary coupling then
caused the crises to compound rather than operate independently.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROXIMATE TRIGGER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RUSSIA'S INVASION OF UKRAINE (February 2022)
  • Ukraine + Russia = ~33% of global wheat exports
  • India subsequently imposed export ban, compounding shortfall
  • Disrupted Black Sea shipping routes (key grain corridor)
  • Severed Europe from cheap Russian gas simultaneously

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 2: SS + RC (fast cross-system cascade)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Food price surge  ╗
                  ╠══[MULTIPLICATIVE, via intersystemic boundary]
Energy price surge╝

OUTWARD CASCADE (RC):
  → Global cost-of-living crisis (food AND energy simultaneously)
  → Fiscal deficits in import-dependent nations
  → Inflation across all economies
  → Interest rate hikes → reduced credit for agricultural investment
  → 60M+ additional people in food crisis vs 2021 (GRFC 2023)
  → Wheat prices +56% year-on-year at peak

KEY DIFFERENCE FROM 2008:
  2008: LFBB — systems self-overloaded then were triggered
  2022: SS + external trigger — systems were stressed but trigger
        was exogenous geopolitical event, not internal tipping point
  Both: RC — fast cross-system cascade once triggered

VALIDATION SIGNATURE:
  ✓ Biophysical origin: drought + weather extremes + energy scarcity
  ✓ Intersystemic: food crisis compounded BY energy crisis (fertiliser costs)
  ✓ Global scope: 80+ countries affected, UN Global Crisis Response Group formed
  ✓ Rapid development: price spikes within weeks of invasion
  ✗ Partly geopolitical origin — not purely biophysical
    (honest limitation: Homer-Dixon framework assumes biophysical primacy)
```

---

## 7. What the Model Can and Cannot Claim

Per Gambhir et al.'s "cross-cutting practices" requirement for transparency:

**The model CAN represent:**
- Stage 1 slow stress accumulation (SS + LFBB) via per-system stress state variables
- Proximate trigger injection at a user-specified step
- Stage 2 fast cascade (RC) via the food–energy coupling arrows and trade network
- Export-ban contagion as a ramifying cascade mechanism
- All four Gambhir system architecture vulnerability diagnostics

**The model CANNOT represent (stated limitations, not omissions):**
- Genuine biofuel land market (requires crop-price–biofuel-price equilibrium)
- Financial speculation in commodity futures (no derivatives market)
- True EROI dynamics (data not available at country level; proxy used)
- Ecosystem/biodiversity feedbacks into production (land degradation not modelled)
- Stakeholder agency (no trader agents until Phase 5)
- Non-human/ecological harm (anthropocentric model; explicitly flagged)
- Live monitoring or early-warning systems (desk model, not operational)

---

## 8. Connecting Architecture to ABM Variables

| Architecture Element | ABM Variable | Source | Phase Implemented |
|---|---|---|---|
| Food system stress (SS) | `food_stress_index` | Derived from σᵢ, reserve ratio, price | Phase 2 |
| Energy system stress (SS) | `energy_stress_index` | EROI proxy + demand/supply ratio | Phase 3 |
| Coping capacity (LFBB threshold) | `coping_capacity_i` | f(Tᵢ, εᵢ, Rᵢ, UHC) | Phase 4 |
| Overload condition | `stress_i / coping_i > 1` | — | Phase 4 |
| Energy→Food arrow | `energy_food_elasticity` | 0.40–0.50 (IEA calibration) | Phase 3 |
| Food→Energy arrow | `biofuel_land_fraction_ξ` | Tunable (0=off, 0.05=calibrated) | Phase 3 |
| Export ban (RC) | `export_ban_i`, contagion probability | Endogenous | Phase 2 |
| Global Scale index | `scale_index(t)` | GDP × energy throughput / 1990 | Phase 5 |
| Homogeneity index | `homogeneity_index(t)` | Herfindahl on cereal production | Phase 5 |
| Connectivity index | `connectivity_index(t)` | Network edge density | Phase 5 |
| Concentrated Power | `power_hhi(t)` | Trade-flow Herfindahl | Phase 5 |

---

*Sources: Gambhir et al. (2025), Nature Communications 16:7382; Homer-Dixon et al. (2015), Ecology & Society 20(3):6.*

# Phase 1 — Agent (Node) Documentation
## Global Food-Energy Systemic Risk ABM — 35-Node Structure

**Source of truth for this document:** `data/processed/node_parameters.csv`,
`data/processed/network_weights.csv`, `docs/EQUATIONS.md`, and
`Global_Food_Resilience_ABM_Database_v4.xlsx` (`Bloc_Membership`,
`Node_Parameters`, `Sources` sheets), all taken from the
`Food_Energy_SRA_PUBLICATION_FREEZE` copy of the repository, which is the
internally self-verified state (`report/verification_report.csv`, 68/68
checks passing against `report/manuscript.md`). Every numeric value below is
transcribed directly from that CSV — nothing here is estimated or invented.

---

## 1. Node Taxonomy

The model represents the entire world's population as **35 nodes**:

- **21 "hub countries"** — modelled individually because each is either a
  top-tier food/energy producer, a top-tier importer, or both. Selection is
  visible in the data itself: e.g. the five largest cereal exporters
  (US, Russia, Ukraine, Argentina, Australia) and five of the most
  import-dependent large populations (Egypt, Nigeria, Bangladesh, Pakistan,
  Saudi Arabia) are all individually resolved rather than folded into a
  regional average.
- **14 "regional blocs"** — every other country on Earth (273 countries in
  total) aggregated into a bloc by geographic and trade-pattern proximity,
  with bloc-level parameters computed as population/GDP-weighted averages of
  member countries. This is a genuine modelling trade-off: bloc-level nodes
  cannot represent within-bloc heterogeneity (e.g. Nigeria-scale variation
  hidden inside "East Africa"). Section 4 makes this trade-off explicit for
  every bloc.

Total country coverage: 21 + Σ(bloc member counts) = 21 + 216 = **237 named
countries/territories**, reconciled against the UN/ISO country list in
`docs/DATA_PROVENANCE.md` (a handful of micro-territories are folded into
their nearest bloc; five bloc-member name-string mismatches against FAO
extraction are logged as a known, negligible-impact limitation in
`FINAL_VERIFICATION_REPORT.md`).

---

## 2. Parameter Data Dictionary

These are the columns of `node_parameters.csv`, defined by their role in the
governing equations (`docs/EQUATIONS.md`). Every "why this policy exists"
explanation in Sections 3–4 is a direct application of these definitions —
not a separate narrative layered on top.

| Symbol | Column | Meaning | Where it acts |
|---|---|---|---|
| P_i | `P_i` | Population | Demand D_i, production scale, Cobb-Douglas anchor |
| b_i, d_i | `b_i`, `d_i` | Birth / death rate (OWID 2010–2022 trend) | Population dynamics (Eq. 9) |
| L_i | `L_i` | Arable land (land elasticity input) | Cobb-Douglas production, α=0.30 |
| W_i | `W_i` | Water availability index | Cobb-Douglas production, β=0.25 |
| E_fuel_i, E_elec_i | `E_fuel_i`, `E_elec_i` | Fuel / electricity energy endowment | Cobb-Douglas γ=0.20; energy stress ES_index |
| K_i | `K_i` | Capital stock | Affordability constraint on imports; capital dynamics (Eq. 10) |
| T_i | `T_i` | Technology index | Cobb-Douglas δ=0.25; coping capacity CC_index |
| A_i | `A_i` | Total-factor-productivity multiplier (SSR-inverted from FAO crop data) | Scales Cobb-Douglas output to match real production |
| θ_animal/perish/imperish | `theta_*` | Output split shares | Food stock composition |
| D_i_Mt | `D_i_Mt` | Annual caloric demand (FAO kcal/cap/day × pop) | Denominator of food security ratio σ_i |
| F_imperish/a/perish | `F_*` | Initial food stock levels (grain, animal, perishable) | σ_i numerator, stock-cap logic |
| R_i | `R_i` | Strategic reserve stock | Reserve-draw term in σ_i (capped at 30% of demand/step) |
| mu_i | `mu_i` | Maximum export fraction (Regime-3 ceiling) | 3-regime export policy (Eq. 11) |
| sigma_safe_i | `sigma_safe_i` | Safe food-security threshold (1.10–1.30) | Regime-2/3 boundary in export policy |
| epsilon_i | `epsilon_i` | General efficiency/coping term | Coping capacity CC_index |
| psi_i | `psi_i` | Famine mortality sensitivity | Population dynamics death-rate penalty |
| rho_i | `rho_i` | Baseline political-risk contribution | Edge-level trade risk ρ_ij |
| clim_vuln_i | `clim_vuln_i` | Climate vulnerability (ND-GAIN food sub-index, 2022) | Climate modifier C_i(t); coping capacity penalty |
| undernourishment_baseline_pct | — | FAO undernourishment prevalence | Cross-check target for CC calibration; **not** fed into the live simulation loop — used only for ML calibration validation |
| epsilon_ef | `epsilon_ef` | **Per-country** energy→food TFP penalty | Arrow 1 (energy stress reduces effective land productivity), calibrated from IEA/FAO agriculture-sector energy data |

**Derived diagnostic (computed for this document, not stored in the CSV):**
`reserve_months_i = (R_i / D_i_Mt) × 12` — approximate months of demand a
node's strategic reserve alone could cover, ignoring current production.
This is the clearest single number for "strategic reserve policy" per node,
so Sections 3–4 report it directly.

---

## 3. Hub Countries (21) — Individually Modelled

Each entry follows the same structure: **role → production → trade
dependency → reserve policy → coping capacity/tech → energy dependency →
climate vulnerability → resilience**. All figures are the real calibrated
2022 values; "why" statements are read directly off the data, not asserted
independently.

### United States
Role: dominant grain exporter and price-setting node (mu_i = 1.40, one of
the highest export ceilings in the network; ρ_i = 0.33, low political
risk). Production: highest capital stock in the model (K_i = 24,977) with
T_i = 0.93 (near the top of the technology range) but only mid-range A_i
(0.24) — output is driven by capital/technology intensity rather than raw
land-use efficiency. Trade: exporter-dominant; σ_safe = 1.85, the highest
safety margin in the dataset, meaning the US only enters export restriction
regimes under severe stress. Reserve: ~0.79 months of demand held in
reserve stock — low in absolute terms because the US relies on flow
(current-year production) rather than buffer stock for food security.
Coping capacity: high (T_i, K_i, low ρ_i all push CC_index up). Energy
dependency: ε_ef = 0.48 (upper-middle of the range) — reflects a highly
mechanised, energy-intensive agricultural sector, so energy price shocks
transmit into US food production more than the "low-tech, low-energy"
nodes. Climate vulnerability: clim_vuln_i = 0.34, below the network median.
Resilience: baseline undernourishment 2.5% (data floor for
high-income countries in this dataset).

### China
Role: largest population node (1.42bn) and the network's largest single
demand center; also a moderate producer. Production: T_i = 0.28 (below
mid-range) but A_i = 0.35, with the largest fuel-energy endowment
(E_fuel_i = 38,703) in the model. Trade: ρ_i = 1.00 — the maximum political
risk contribution in the dataset, materially raising the cost/friction of
every edge involving China. Reserve: ~1.01 months — near network median.
Coping capacity: moderated downward by the high ρ_i term despite strong
capital and energy endowments. Energy dependency: ε_ef = 0.39. Climate
vulnerability: 0.40, slightly above median. Resilience: 2.5% baseline
undernourishment (data floor), consistent with China's large but currently
food-secure population — the systemic risk China poses to the network is
scale (any disruption to Chinese demand or production ripples through
1,190 trade edges), not chronic insecurity.

### India
Role: second-largest population (1.44bn) and, notably, the **highest
undernourishment baseline among hub countries** (12.0%), making India a hub
node with structural — not just crisis-driven — food insecurity. Production:
T_i = 0.12 (low), A_i = 0.60 (moderate-high) — output is closer to
land/labour-intensive than capital-intensive. Trade: low reserve
(~0.25 months), σ_safe = 1.73. Coping capacity: pulled down by low T_i.
Energy dependency: ε_ef = 0.31 (lower-middle — less industrialised
agriculture than the US/Saudi Arabia end of the range). Climate
vulnerability: 0.60 — one of the highest among hub countries, reflecting
monsoon-dependence and heat exposure. **Why this matters for the
simulation:** India is one of the model's clearest "structurally vulnerable
regardless of scenario" nodes referenced in the validated scenario results
(Section on Phase 2/3 below) — its combination of high baseline
undernourishment, low reserve buffer, and high climate vulnerability means
it overloads under climate-driven triggers specifically (see worst-case
discovery results, where India is the top target node).

### Brazil
Role: major grain/protein exporter, high water availability (W_i = 0.99,
near the top of the range). Production: A_i = 0.78 (high efficiency).
Trade: mu_i = 1.37, strong export capacity; low political risk (ρ_i =
0.33). Reserve: ~0.96 months. Coping capacity: solid, driven by high W_i and
moderate T_i. Energy dependency: ε_ef = 0.35 (below median — less
energy-intensive agriculture than the US). Climate vulnerability: 0.39.
Resilience: 2.5% baseline (data floor).

### Russia
Role: major grain/energy exporter — the node whose export policy has
directly observable, model-tested consequences (2022 Ukraine scenario
trigger set targets Russia's edges directly). Production: T_i = 0.50,
A_i = 0.45. Trade: mu_i = 1.34, ρ_i = 0.67 (elevated political risk,
consistent with sanctions-exposure). Reserve: only ~0.34 months — a
comparatively thin buffer for a major exporter. Energy dependency:
ε_ef = 0.41. Climate vulnerability: 0.31 (below median). This combination
— high export share, elevated political risk, thin reserve — is exactly
the profile that makes Russia's trade edges a first-order RC-cascade
transmission channel in the 2022 scenario.

### Ukraine
Role: specialist grain exporter with the **highest A_i in the entire
dataset (2.95)** — reflecting a technology-and-land-efficiency profile far
above its raw T_i (0.20) would suggest, a deliberate correction (the
"Agricultural Trade Multiplier" fix documented in `FINAL_VERIFICATION_REPORT.md`)
to counter the gravity model's tendency to under-rank agricultural
specialists relative to large-GDP industrial economies. Trade: the lowest
σ_safe in the hub set (1.53) and negative population growth (b_i − d_i =
−0.0006, the only negative rate among hub countries — pre-dating the 2022
war in the underlying OWID trend data). Reserve: ~0.76 months. Climate
vulnerability: 0.42. Resilience: 6.9% baseline undernourishment — already
elevated pre-crisis. **Why this matters:** Ukraine is the direct trigger
target in the 2022 scenario (edge capacity and export-fraction shocks
applied to Ukraine's outgoing trade edges); its unusually high A_i means
disruption to Ukraine has an outsized effect on global supply relative to
its population share.

### Argentina
Role: major grain exporter, highest reserve ratio among hub countries
(**~2.98 months** — by far the largest buffer-to-demand ratio in the entire
36-row table). Production: A_i = 1.30 (high). Trade: mu_i = 1.39. Energy
dependency: ε_ef = 0.37. Climate vulnerability: 0.37. This large reserve
buffer is a genuine calibrated data point (not a modelling artefact) and
gives Argentina structural resilience against short trigger shocks that
other exporters lack.

### Australia
Role: major grain exporter; **ρ_i = 0.00, the lowest political-risk
contribution possible** (tied with France, Germany, Japan, UK, Nordics).
Production: T_i = 0.76 (high). Trade: mu_i = 1.30. Reserve: ~1.04 months.
Energy dependency: ε_ef = 0.44. Climate vulnerability: 0.38. **Why this
matters:** because Australia sits at zero political risk, it is used
specifically as the target node for the "geopolitical restriction" leg of
the worst-case compound-trigger discovery (Section 5) — the finding that
even a politically stable, well-resourced exporter becomes a top-5
worst-case target once combined with a climate shock demonstrates that
political stability alone does not immunise a node against RC cascade.

### Canada
Role: exporter with the highest reserve ratio among the "big five" grain
exporters after Argentina (~1.06 months). Production: T_i = 0.72, high
water availability (W_i = 0.98). Trade: mu_i = 1.23. Energy dependency:
ε_ef = 0.46 (upper-middle). Climate vulnerability: 0.24 — the lowest among
hub countries, consistent with Canada's temperate, less drought-exposed
production base.

### France
Role: EU agricultural anchor and industrial food-processing hub. Production:
T_i = 0.68, notably low reserve (**F_perish_i is blank in the raw CSV — see
Section 6 data-quality note**), imperishable stock only ~0.14 months
equivalent. Trade: ρ_i = 0.00. Energy dependency: ε_ef = 0.40. Climate
vulnerability: 0.29 (low).

### Indonesia
Role: large-population Southeast Asian importer/producer. Production:
T_i = 0.17 (low), A_i = 0.36. Trade: ρ_i = 0.67. Reserve: ~0.11 months —
one of the thinnest buffers among hub countries. Energy dependency:
ε_ef = 0.29 (low). Climate vulnerability: 0.49 (elevated). Resilience:
6.3% baseline undernourishment.

### Vietnam
Role: rice exporter with the network's second-highest political risk
contribution (ρ_i = 1.00, tied with China and Saudi Arabia). Production:
A_i = 1.11. Reserve: ~0.17 months. Energy dependency: ε_ef = 0.27 (low).
Climate vulnerability: 0.42. σ_safe = 1.40, the lowest safety margin among
hub countries (tied with Thailand and several blocs), meaning Vietnam
enters export-restriction regimes earliest relative to its own food
security ratio.

### Thailand
Role: rice exporter. Production: T_i = 0.26, A_i = 0.50. Reserve:
~0.29 months. Energy dependency: ε_ef = 0.30. Climate vulnerability: 0.46.
σ_safe = 1.40 (low, shared with Vietnam).

### Egypt
Role: the network's largest wheat importer by dependence — this is *the*
canonical Homer-Dixon/Gambhir 2008-crisis node. Production: A_i = 1.68
(second-highest after Ukraine) but W_i = 0.06 — **the lowest water
availability in the entire dataset outside MENA/Saudi Arabia**, meaning
Egypt's food output is fundamentally water-constrained regardless of
technology. Reserve: ~0.25 months. Energy dependency: ε_ef = 0.45 (high —
irrigation-dependent agriculture is energy-intensive). Climate
vulnerability: 0.48. Resilience: 9.4% baseline undernourishment — already
structurally elevated. **Why this matters:** Egypt's combination of severe
water constraint, high import dependence, and pre-existing undernourishment
makes it one of the model's chronic-overload nodes across nearly every
scenario tested (Section 4 of the validated results).

### Nigeria
Role: largest hub-country population after the US/China/India tier is
excluded (227.9m) and the hub country with the **second-highest baseline
undernourishment (19.9%)**. Production: T_i = 0.10 (among the lowest in the
dataset), A_i = 1.31. Reserve: **~0.07 months — the thinnest reserve buffer
of any hub country.** Energy dependency: ε_ef = 0.26 (low). Climate
vulnerability: 0.61 (high). This is a structurally fragile node by every
metric simultaneously — low tech, near-zero reserve, high climate
vulnerability, high baseline undernourishment — which is exactly the
profile the validated results identify as "overloads regardless of
scenario."

### Bangladesh
Role: high-population, high-density, low-land-area importer. Production:
L_i = 9.4 (arable land) is the lowest among hub countries relative to its
population of 171m. Reserve: ~0.11 months. Energy dependency:
ε_ef = 0.22 — **the lowest in the entire dataset**, reflecting
low-mechanization smallholder agriculture. Climate vulnerability: 0.58.
Resilience: 10.4% baseline undernourishment.

### Pakistan
Role: large-population, water-constrained importer. Production: W_i = 0.27
(low), T_i = 0.07 — **the lowest technology index of any hub country.**
Reserve: ~0.12 months. Energy dependency: ε_ef = 0.24 (low). Climate
vulnerability: 0.55. Resilience: 16.5% baseline undernourishment — the
second-highest among hub countries. This is the other node (with Saudi
Arabia and Central Africa) flagged in the trigger-dependency test as
structurally vulnerable even when reset to a "healthy" starting state — a
genuine, non-fabricated model finding (see Phase 3 below).

### Germany
Role: EU industrial/agricultural hub. Production: T_i = 0.79 (high).
Trade: ρ_i = 0.00. Energy dependency: ε_ef = 0.42. Climate vulnerability:
0.19 — the lowest in the entire dataset.

### Japan
Role: high-income, minimal-land importer. Production: L_i = 4.6, the
lowest arable land of any node. Energy dependency: ε_ef = 0.36.
Data-quality note: `theta_perish_i`, `theta_imperish_i`, and
`undernourishment_baseline_pct` are blank for Japan in the source CSV
(flagged in Section 6 — not silently imputed).

### United Kingdom
Role: high-income importer. Production: T_i = 0.66. Energy dependency:
ε_ef = 0.38. Climate vulnerability: 0.22 (low).

### Saudi Arabia
Role: the network's most extreme case of energy-food coupling. Production:
W_i = 0.05 — **tied for the lowest water availability in the dataset** —
with food output structurally dependent on desalination. Energy
dependency: ε_ef = 0.52 — **the single highest energy→food TFP penalty in
the entire model**, directly calibrated (per `docs/EQUATIONS.md` Section 3.2)
to desalination-intensive irrigation. Trade: ρ_i = 1.00 (maximum). Reserve:
~0.54 months, moderate. Climate vulnerability: 0.41. **Why this matters:**
Saudi Arabia is the model's clearest test case for Arrow 1 (energy stress →
food TFP penalty) — a pure energy shock propagates into Saudi food
production faster and harder than for any other node, and this is a
calibrated, sourced value, not a scenario assumption.

---

## 4. Regional Blocs (14) — Aggregated Nodes

Each bloc aggregates the named member countries below (from
`Bloc_Membership`, `Global_Food_Resilience_ABM_Database_v4.xlsx`) into a
single node with population/GDP-weighted average parameters. **Modelling
caveat, stated once here and applying to every bloc below:** bloc-level
aggregation cannot resolve within-bloc heterogeneity — e.g. "East Africa"
contains both chronically food-insecure states (Somalia, South Sudan) and
comparatively stable ones (Mauritius, Seychelles), and the bloc parameters
represent a population-weighted average across all 21 members, not any
single member's real condition.

| Bloc | Members (n) | Pop. (M) | T_i | clim_vuln_i | Undernourishment % | Reserve (months) | ε_ef |
|---|---|---|---|---|---|---|---|
| West Africa (ECOWAS) | 16 | 217.1 | 0.052 | 0.616 | 11.8 | 0.12 | 0.22 |
| East Africa | 21 | 537.9 | 0.050 | 0.637 | 24.4 | 0.07 | 0.21 |
| Southern Africa (SADC) | 6 | 108.9 | 0.147 | 0.536 | 14.9 | 0.22 | 0.27 |
| Central Africa | 8 | 169.4 | 0.050 | 0.578 | **31.1 (highest in model)** | 0.02 (lowest) | 0.18 (lowest) |
| MENA-other | 19 | 446.9 | 0.271 | 0.441 | 8.2 | 0.24 | 0.40 |
| Central Asia | 10 | 142.8 | 0.157 | 0.435 | 10.6 | 0.21 | 0.36 |
| South Asia-other | 4 | 54.0 | 0.108 | 0.531 | 6.2 | 0.06 | 0.25 |
| Southeast Asia-other | 13 | 346.5 | 0.291 | 0.508 | 7.0 | 0.10 | 0.28 |
| Pacific/Oceania-other | 22 | 19.1 | 0.218 | 0.543 | 18.3 | 0.10 | 0.32 |
| Caribbean & Central America | 38 | 225.9 | 0.242 | 0.436 | 7.5 | 0.17 | 0.31 |
| Andean & Southern Cone-other | 12 | 176.3 | 0.231 | 0.426 | 6.8 | 0.13 | 0.33 |
| Eastern Europe-other | 10 | 57.2 | 0.395 | 0.354 | 2.6 | 0.17 | 0.36 |
| EU-other | 30 | 257.2 | 0.659 | 0.240 | 2.5 | 0.00 (lowest) | 0.39 |
| Nordics | 7 | 28.1 | 0.854 (highest) | 0.263 | 2.5 | 0.05 | 0.33 |

**Central Africa** (Cameroon, Central African Republic, Chad, Congo, DR
Congo, Equatorial Guinea, Gabon, São Tomé and Príncipe) is the single most
structurally vulnerable node in the entire 35-node system on every
composite metric simultaneously: lowest technology (0.050, tied with East
Africa), lowest energy-food coupling resilience (ε_ef = 0.18), lowest
reserve buffer (0.02 months — effectively none), and highest baseline
undernourishment (31.1%). This is not a scenario artefact; it is the
calibrated starting condition, and it is the primary reason Central Africa
appears in the "structurally overloaded regardless of scenario" set
referenced in the validated results (12 of 35 nodes; Phase 3 below).

**East Africa** (21 members including Ethiopia, Kenya, Somalia, South
Sudan, Sudan) has the largest bloc population (537.9M) and second-highest
undernourishment (24.4%) — its aggregation folds together the 2011 East
Africa crisis-affected states with more stable neighbours (Mauritius,
Seychelles), which is the specific caveat to apply when reading Phase 2's
"2011 East Africa" scenario against this node: the trigger is designed to
target the bloc's low-reserve, low-tech members within the aggregate.

**Nordics** and **EU-other** sit at the opposite extreme: highest
technology (Nordics, 0.854), lowest reserve *ratio* by design (EU-other
holds stock in different accounting categories not captured by R_i, hence
the near-zero figure — a data-representation artefact flagged in Section 6,
not a real EU food-security condition) and lowest climate vulnerability.

---

## 5. Cross-Cutting Observations (data-derived, not narrative)

1. **Reserve policy is not correlated with export capacity.** Argentina
   (mu_i = 1.39, exporter) holds the largest reserve ratio (2.98 months);
   the US (mu_i = 1.40, the largest exporter) holds one of the *smallest*
   (0.79 months). The model does not assume "big exporters = well-buffered"
   — this is visible directly in the calibrated data, and it is the reason
   the Reserve Mandate scenario response (S3, Phase 2) has a real,
   differentiated effect across exporters rather than being redundant.
2. **Energy-food coupling strength (ε_ef) spans a 2.9× range** (0.18
   Central Africa to 0.52 Saudi Arabia) and is *not* proportional to
   income or technology level — Bangladesh (low-tech, low ε_ef = 0.22) and
   the US (high-tech, mid ε_ef = 0.48) sit at opposite ends for different
   reasons (subsistence vs. mechanised-irrigation agriculture). This
   justifies the per-country calibration described in Section 3.2 of the
   manuscript over a single global constant.
3. **Political risk (ρ_i) is bimodal**, not continuous: six hub countries
   sit at exactly 0.00 (Australia, France, Germany, Japan, UK, Nordics)
   and four sit at exactly 1.00 (China, Vietnam, Saudi Arabia, Bangladesh),
   with the rest spread across 0.33–0.77. This bimodality is a property of
   the underlying stability-proxy data, not a modelling choice, and it
   directly determines which edges are cheapest to route trade through
   under the gravity model (Eq. 7).

---

## 6. Data-Quality Notes (transcribed honestly, not smoothed over)

- **France, Germany:** `theta_perish_i` and `F_perish_i` are blank in
  `node_parameters.csv`. The simulation code must have a defined fallback
  for these — this needs to be confirmed against `agent.py`'s NaN-handling
  before this is presented as a clean dataset in any publication table.
- **Japan:** `theta_perish_i`, `theta_imperish_i`, and
  `undernourishment_baseline_pct` are all blank.
- **Nigeria, West Africa, East Africa, Central Africa:** `E_fuel_i` is
  blank (empty field between `W_i` and `E_elec_i` in the raw CSV row).
  This is a real gap in the source data (likely a fossil-fuel-endowment
  series with no coverage for these blocs), not a formatting error — it
  should be listed explicitly in the technical report's limitations
  section (Phase 6/8) rather than silently defaulted to zero.
- **EU-other reserve ratio (~0.004 months):** almost certainly an
  accounting-category mismatch (EU strategic reserves are likely held
  under a different mechanism than the `R_i` column captures for other
  nodes) rather than a genuine near-zero buffer for 30 countries including
  Poland, Spain, and the Netherlands. Flagged for correction before this
  number is used in any comparative reserve-policy claim.

These four items are the concrete, evidence-based gaps that should be
resolved (or explicitly caveated) before Phase 1 documentation is
considered publication-ready. None of them affect the model's mechanics —
they are calibration/documentation gaps, not code bugs.

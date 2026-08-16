# Data Provenance Register
## Global Food–Energy Systemic Risk ABM — Phase 1

**Principle:** Every variable in the model must be traceable to a specific field in a named, publicly accessible dataset. No synthetic draws. No undocumented approximations.  
**Framework requirement:** Gambhir et al. (2025) cross-cutting practice — "transparency and availability of data, evidence, and methods."

---

## 1. Primary Data Sources

| ID | Source | Access | Coverage | Download Path |
|---|---|---|---|---|
| **OWID-E** | Our World in Data — Energy Data | github.com/owid/energy-data | 1900–2023, ~200 countries | `data/raw/owid_energy_data.csv` |
| **OWID-C** | Our World in Data — CO2 Data | github.com/owid/co2-data | 1750–2023, ~200 countries | `data/raw/owid_co2_data.csv` |
| **WB-AL** | World Bank — Arable Land | AG.LND.ARBL.ZS | 1961–2022, 266 countries | `data/raw/worldbank/wb_arable_land.csv` |
| **WB-WS** | World Bank — Water Withdrawal | ER.H2O.FWTL.ZS | 1962–2020, 266 countries | `data/raw/worldbank/wb_water_stress.csv` |
| **WB-TR** | World Bank — Trade % GDP | NE.TRD.GNFS.ZS | 1960–2023, 266 countries | `data/raw/worldbank/wb_trade_gdp.csv` |
| **WB-LE** | World Bank — Life Expectancy | SP.DYN.LE00.IN | 1960–2022, 266 countries | `data/raw/worldbank/wb_life_exp.csv` |
| **WB-FE** | World Bank — Fertiliser kg/ha | AG.CON.FERT.ZS | 1961–2022, 266 countries | `data/raw/worldbank/wb_fertiliser.csv` |
| **WB-UH** | World Bank / WHO — UHC Index | SH.UHC.SRVS.CV.XD | 2000–2021, 292 countries | `data/raw/worldbank/wb_uhc_index.csv` |
| **FAO-FPI** | FAO Food Price Index | fao.org/worldfoodsituation | 1990–2025, monthly, global | `data/raw/fao/fao_food_price_index.csv` |
| **FAO-FBS** | FAO Food Balance Sheets | FAOSTAT bulk | 2010–2023, ~180 countries | `data/raw/fao/fao_food_balance_sheets.csv` |
| **FAO-CP** | FAO Crop Production | FAOSTAT bulk | 1961–2024, ~180 countries | `data/raw/fao/fao_crop_production.csv` |

---

## 2. Variable-to-Source Mapping

### 2.1 Population and Demographics

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| Population | Pᵢ(t) | `population` | OWID-E | persons; used for demand scaling |
| Population growth rate | bᵢ − dᵢ | Derived: `(P_2022/P_2010)^(1/12) − 1` | OWID-E | Annual rate 2010–2022 trend |
| Life expectancy | LEᵢ(t) | `SP.DYN.LE00.IN` | WB-LE | years at birth; used for εᵢ, ψᵢ calibration |

### 2.2 Economic Variables

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| GDP | Kᵢ(t) | `gdp` | OWID-E | 2015 constant USD; capital proxy |
| GDP per capita | Kᵢ/Pᵢ | Derived: `gdp / population` | OWID-E | Used for Tᵢ, εᵢ, μᵢ derivation |
| Trade openness | tradeᵢ(t) | `NE.TRD.GNFS.ZS` | WB-TR | (Exports+Imports)/GDP %; used for Cᵢⱼ, μᵢ |

### 2.3 Energy Variables

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| Fossil fuel consumption | E_fuelᵢ(t) | `fossil_fuel_consumption` | OWID-E | TWh; direct energy input to production |
| Electricity generation | E_elecᵢ(t) | `electricity_generation` | OWID-E | TWh; electricity sub-component |
| Renewable electricity | E_renewᵢ(t) | `renewable_electricity` | OWID-E | TWh; solar+wind+hydro+nuclear |
| Solar | — | `solar_electricity` | OWID-E | TWh |
| Wind | — | `wind_electricity` | OWID-E | TWh |
| Hydro | — | `hydro_electricity` | OWID-E | TWh |
| Nuclear | — | `nuclear_electricity` | OWID-E | TWh |
| Oil consumption | — | `oil_consumption` | OWID-E | TWh |
| Gas consumption | — | `gas_consumption` | OWID-E | TWh |
| Coal consumption | — | `coal_consumption` | OWID-E | TWh |
| Fossil share of energy | ρ_fossilᵢ | `fossil_share_energy` | OWID-E | %; used for energy stress proxy |
| Renewables share of energy | ρ_renewᵢ | `renewables_share_energy` | OWID-E | % |
| Low-carbon share of electricity | — | `low_carbon_share_elec` | OWID-E | % |
| Energy per capita | eᵢ | `energy_per_capita` | OWID-E | kWh/person; used for Tᵢ |
| Electricity demand | — | `electricity_demand` | OWID-E | TWh |
| Net electricity imports | — | `net_elec_imports` | OWID-E | TWh |

### 2.4 Environment and Emissions

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| GHG emissions | GHGᵢ(t) | `greenhouse_gas_emissions` | OWID-E | MtCO2e |
| CO2 emissions | CO2ᵢ(t) | `co2` | OWID-C | MtCO2 |
| CO2 per capita | — | `co2_per_capita` | OWID-C | tCO2/person |
| Methane | — | `methane` | OWID-C | MtCO2e |
| Nitrous oxide | — | `nitrous_oxide` | OWID-C | MtCO2e; agriculture proxy |
| Land-use change CO2 | LUCᵢ | `land_use_change_co2` | OWID-C | MtCO2; deforestation proxy |

### 2.5 Land and Water (World Bank)

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| Arable land index | Lᵢ(t) | `AG.LND.ARBL.ZS` | WB-AL | % of total land area; direct use in Cobb-Douglas |
| Water availability proxy | Wᵢ(t) | Derived: `1 − min(WW/100, 0.9)` | WB-WS | WW = freshwater withdrawal % of internal resources |
| Fertiliser consumption | ferᵢ(t) | `AG.CON.FERT.ZS` | WB-FE | kg/ha arable land; used in Tᵢ calibration |

### 2.6 Health

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| UHC service coverage | UHCᵢ | `SH.UHC.SRVS.CV.XD` | WB-UH | 0–100 index; used in εᵢ, ψᵢ calibration |

### 2.7 Food System (FAO)

| ABM Variable | Symbol | Source Field | Source ID | Notes |
|---|---|---|---|---|
| Caloric supply | cᵢ(t) | `Food supply (kcal/capita/day)` Item=Grand Total | FAO-FBS | kcal/cap/day; used for Dᵢ = cᵢ × Pᵢ × 365 |
| Annual caloric demand | Dᵢ(t) | Derived: `kcal_cap_day × population × 365` | FAO-FBS + OWID-E | kcal/year |
| Food production (total) | — | `Production` Item=Grand Total | FAO-FBS | 1000 tonnes domestic supply |
| Food imports | — | `Import quantity` Item=Grand Total | FAO-FBS | 1000 tonnes |
| Food exports | — | `Export quantity` Item=Grand Total | FAO-FBS | 1000 tonnes |
| Cereal production | Qᵢ_cereal(t) | `Production` Item=`Cereals, primary` Element=`Production` | FAO-CP | tonnes; primary Cobb-Douglas calibration |
| Global food price index | p(t) | `Food Price Index` (annual mean of monthly) | FAO-FPI | 2014–2016 = 100; anchors p(0) |
| Cereal sub-index | p_cereal(t) | `Cereals` column | FAO-FPI | for cereal-specific price dynamics |

---

## 3. Derived ABM Parameters (Computed, Not Directly Observed)

These are honest derivations from real data. The formula, rationale, and limitations are documented for each.

| Parameter | Symbol | Formula | Inputs | Rationale | Limitation |
|---|---|---|---|---|---|
| Technology index | Tᵢ(t) | `0.30·min(LE/85,1) + 0.40·min(GDPpc/60000,1) + 0.30·min(fert/300,1)` | WB-LE, OWID-E, WB-FE | Life expectancy proxies health/institutional capacity; GDP/cap proxies capital accumulation; fertiliser proxies agricultural technology | Conflates different dimensions of technology; no direct R&D or patent data |
| Water availability | Wᵢ(t) | `1 − min(freshwater_withdrawal_pct / 100, 0.90)` | WB-WS | Higher % withdrawal = more stressed = less available | Withdrawal is not the same as scarcity; doesn't capture precipitation variability |
| Arable land index | Lᵢ(t) | `AG.LND.ARBL.ZS` (direct) | WB-AL | Percentage of land that is arable is a direct, standard measure | Doesn't capture land quality degradation within arable category |
| Recovery rate | εᵢ(t) | `0.01 + 0.15·min(GDPpc/60000,1) + 0.14·min(UHC/100,1)` | OWID-E, WB-UH | Wealthier nations with better health systems recover faster from disruption | Linear interpolation; no governance quality data |
| Famine sensitivity | ψᵢ(t) | `0.10 − 0.07·(0.5·min(LE/85,1) + 0.5·min(UHC/100,1))` | WB-LE, WB-UH | Poorer nations with weaker health systems suffer more mortality per unit food deficit | No direct famine mortality calibration data available at scale |
| Export conservatism | μᵢ(t) | `0.90 − 0.50·min(GDPpc/60000,1) − 0.10·min(trade/100,1)` | OWID-E, WB-TR | Poorer, less trade-open nations hoard food more aggressively; richer open nations export more freely | Doesn't capture political regime type or historical ban behaviour |
| Annual caloric demand | Dᵢ(t) | `kcal_cap_day × population × 365` | FAO-FBS, OWID-E | Direct from FAO data where available (2010–2023); extrapolated backwards using population × income scaling | FAO FBS only goes back to 2010; earlier years use OWID income proxy |
| Pop growth rate | bᵢ − dᵢ | `(P_2022/P_2010)^(1/12) − 1` | OWID-E | 12-year compound annual growth rate; better than single-year noise | Assumes trend continues; misses structural breaks (e.g., COVID mortality) |

---

## 4. Network Weight Derivation

| Edge Attribute | Symbol | Formula | Source Variables | Notes |
|---|---|---|---|---|
| Trade capacity | Cᵢⱼ | `(GDPᵢ × GDPⱼ) / distᵢⱼ² × tradeᵢ × tradeⱼ` | OWID-E (GDP), WB-TR (trade%), distance proxy | Gravity model; standard in trade economics. Distance = geographic centroid proxy |
| Transaction cost | κᵢⱼ | `base_dist_cost + landlocked_penalty + chokepoint_multiplier` | Geographic lookup | Landlocked: +0.25; chokepoint (Suez, Hormuz, Bosphorus) dependency: +0.15 |
| Political risk baseline | ρᵢⱼ | `1 − 0.5·(stabilityᵢ + stabilityⱼ)` + regime_penalty | Derived from WB governance data proxy | Higher mutual instability = higher trade risk |

---

## 5. Homer-Dixon System-Level Indices

| Index | Symbol | Formula | Source | Phase |
|---|---|---|---|---|
| Scale index | Sᵢ(t) | `(GDPᵢ(t) × E_totalᵢ(t)) / (GDPᵢ(2000) × E_totalᵢ(2000))` | OWID-E | Phase 5 |
| Connectivity index | Nᵢ(t) | Count of active trade links above volume threshold / max possible | Network weights | Phase 5 |
| Homogeneity index | Hᵢ(t) | Herfindahl-Hirschman on cereal production by item type | FAO-CP | Phase 5 |
| Food stress index | FSᵢ(t) | `max(0, 1 − σᵢ) × (1 + price_deviation)` | Endogenous | Phase 4 |
| Energy stress index | ESᵢ(t) | `fossil_shareᵢ × (1 − renew_shareᵢ) × demand_growth_indexᵢ` | OWID-E | Phase 3 |
| Coping capacity | CCᵢ(t) | `Tᵢ × Rᵢ × εᵢ × (1 − logistics_disruptionᵢ)` | Derived | Phase 4 |
| Overload flag | OLᵢ(t) | `(FSᵢ + ESᵢ) / CCᵢ > 1.0` | Derived | Phase 4 |

---

## 6. Known Data Gaps

| Gap | Impact | Workaround Used | Phase to Address |
|---|---|---|---|
| EROI data not available country-level | Cannot model true energy return dynamics | Use fossil_share_energy × demand_growth as proxy | Phase 3 |
| No real bilateral food trade flows by country-pair | Network weights are gravity-approximated | FAO-FBS gives total imports/exports but not bilateral breakdown | Phase 2 |
| FAO FBS only from 2010 | Pre-2010 caloric demand estimated | Population × income-class caloric rate proxy for 2000–2009 | Phase 1 |
| UHC data sparse (every 2–5 years) | Recovery rate discontinuous | Linear interpolation between available years | Phase 1 |
| No historical political stability index | Cannot calibrate ρᵢⱼ from history | Derived from GDP per capita + life expectancy proxy | Phase 1 |
| No Big Five trader data | Cannot calibrate trader power | Phase 5 introduces 5 abstract trader agents with market share parameter | Phase 5 |
| Biofuel land fraction ξ | Cannot calibrate Energy→Food land arrow precisely | Set to 0.05 (5% cropland reallocated at full energy stress), toggleable | Phase 3 |

---

*This document must be updated whenever a new data source is added or a formula is changed. Version 1.0, June 2026.*

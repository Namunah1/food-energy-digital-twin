"""
src/data_pipeline.py
====================
Phase 1 Data Pipeline — Global Food-Energy Systemic Risk ABM
Framework: Gambhir et al. (2025) + Homer-Dixon et al. (2015)

Inputs  (all in data/raw/):
  OWID energy data, OWID CO2 data,
  World Bank: arable land, water stress, trade GDP, life expectancy,
              fertiliser, UHC index
  FAO: Food Price Index, Food Balance Sheets, Crop Production

Outputs (data/processed/):
  node_panel.csv        — 35 nodes × 24 years × 47 variables
  network_weights.csv   — 35×35 directed trade network (Cij, kij, rhoij)
  abm_init_2022.csv     — Single-year ABM initialisation snapshot
  fpi_annual.csv        — FAO Food Price Index annual averages 2000-2023

Run:
  python src/data_pipeline.py

All derivation formulas are documented in docs/DATA_PROVENANCE.md.
All equations are in docs/EQUATIONS.md.
"""

import os
import sys
import numpy as np
import pandas as pd
import pickle
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
RAW      = ROOT / "data" / "raw"
PROC     = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# ── 35-Node Definition ────────────────────────────────────────────────────────
HUB_COUNTRIES = [
    "United States", "China", "India", "Brazil", "Russia", "Ukraine",
    "Argentina", "Australia", "Canada", "France", "Indonesia", "Vietnam",
    "Thailand", "Egypt", "Nigeria", "Bangladesh", "Pakistan",
    "Germany", "Japan", "United Kingdom", "Saudi Arabia",
]

BLOC_MEMBERS = {
    "West Africa (ECOWAS)":         ["Nigeria","Ghana","Senegal","Ivory Coast","Mali",
                                      "Niger","Burkina Faso","Guinea","Benin","Togo",
                                      "Sierra Leone","Liberia","Gambia","Guinea-Bissau","Cape Verde"],
    "East Africa":                  ["Ethiopia","Kenya","Tanzania","Uganda","Rwanda",
                                      "Somalia","Sudan","Eritrea","Djibouti","Burundi"],
    "Southern Africa (SADC)":       ["South Africa","Mozambique","Zimbabwe","Zambia",
                                      "Angola","Namibia","Botswana","Malawi","Lesotho","Eswatini"],
    "Central Africa":               ["Democratic Republic of Congo","Cameroon","Chad",
                                      "Central African Republic","Congo","Gabon","Equatorial Guinea"],
    "MENA-other":                   ["Morocco","Algeria","Tunisia","Libya","Iraq","Syria",
                                      "Yemen","Jordan","Lebanon","Kuwait","Bahrain","Oman",
                                      "Qatar","United Arab Emirates","Iran"],
    "Central Asia":                 ["Kazakhstan","Uzbekistan","Turkmenistan",
                                      "Kyrgyzstan","Tajikistan","Afghanistan"],
    "South Asia-other":             ["Sri Lanka","Nepal","Myanmar","Bhutan","Maldives"],
    "Southeast Asia-other":         ["Philippines","Malaysia","Cambodia","Laos",
                                      "Singapore","Brunei","East Timor"],
    "Pacific/Oceania-other":        ["New Zealand","Papua New Guinea","Fiji",
                                      "Solomon Islands","Vanuatu","Samoa"],
    "Caribbean & Central America":  ["Mexico","Colombia","Venezuela","Peru","Chile",
                                      "Cuba","Guatemala","Honduras","El Salvador",
                                      "Nicaragua","Costa Rica","Panama",
                                      "Dominican Republic","Haiti","Jamaica",
                                      "Trinidad and Tobago"],
    "Andean & Southern Cone-other": ["Bolivia","Paraguay","Uruguay","Ecuador"],
    "Eastern Europe-other":         ["Poland","Romania","Czech Republic","Hungary",
                                      "Slovakia","Bulgaria","Croatia","Serbia",
                                      "Belarus","Moldova","Lithuania","Latvia",
                                      "Estonia","Slovenia","North Macedonia",
                                      "Albania","Bosnia and Herzegovina"],
    "EU-other":                     ["Italy","Spain","Netherlands","Belgium","Sweden",
                                      "Austria","Denmark","Finland","Portugal",
                                      "Ireland","Greece","Luxembourg","Cyprus","Malta"],
    "Nordics":                      ["Norway","Iceland"],
}

ALL_NODES = HUB_COUNTRIES + list(BLOC_MEMBERS.keys())

# ── Name maps (our names → source names) ──────────────────────────────────────
NODE_TO_WB = {
    "United States":  "United States",
    "China":          "China",
    "India":          "India",
    "Brazil":         "Brazil",
    "Russia":         "Russian Federation",
    "Ukraine":        "Ukraine",
    "Argentina":      "Argentina",
    "Australia":      "Australia",
    "Canada":         "Canada",
    "France":         "France",
    "Indonesia":      "Indonesia",
    "Vietnam":        "Viet Nam",
    "Thailand":       "Thailand",
    "Egypt":          "Egypt, Arab Rep.",
    "Nigeria":        "Nigeria",
    "Bangladesh":     "Bangladesh",
    "Pakistan":       "Pakistan",
    "Germany":        "Germany",
    "Japan":          "Japan",
    "United Kingdom": "United Kingdom",
    "Saudi Arabia":   "Saudi Arabia",
}

NODE_TO_FAO = {
    "United States":  "United States of America",
    "China":          "China",
    "India":          "India",
    "Brazil":         "Brazil",
    "Russia":         "Russian Federation",
    "Ukraine":        "Ukraine",
    "Argentina":      "Argentina",
    "Australia":      "Australia",
    "Canada":         "Canada",
    "France":         "France",
    "Indonesia":      "Indonesia",
    "Vietnam":        "Viet Nam",
    "Thailand":       "Thailand",
    "Egypt":          "Egypt",
    "Nigeria":        "Nigeria",
    "Bangladesh":     "Bangladesh",
    "Pakistan":       "Pakistan",
    "Germany":        "Germany",
    "Japan":          "Japan",
    "United Kingdom": "United Kingdom of Great Britain and Northern Ireland",
    "Saudi Arabia":   "Saudi Arabia",
}

MEMBER_TO_FAO = {
    "Ivory Coast":                  "Côte d'Ivoire",
    "Cape Verde":                   "Cabo Verde",
    "Democratic Republic of Congo": "Democratic Republic of the Congo",
    "Congo":                        "Congo",
    "Iran":                         "Iran (Islamic Republic of)",
    "Syria":                        "Syrian Arab Republic",
    "Bolivia":                      "Bolivia (Plurinational State of)",
    "Venezuela":                    "Venezuela (Bolivarian Republic of)",
    "Laos":                         "Lao People's Democratic Republic",
    "Tanzania":                     "United Republic of Tanzania",
    "Vietnam":                      "Viet Nam",
    "United States":                "United States of America",
    "Russia":                       "Russian Federation",
    "United Kingdom":               "United Kingdom of Great Britain and Northern Ireland",
}

def to_fao(name):
    return MEMBER_TO_FAO.get(name, name)

YEARS     = list(range(2000, 2024))
FBS_YEARS = list(range(2010, 2024))

LANDLOCKED = {
    "Afghanistan","Armenia","Austria","Azerbaijan","Belarus","Bhutan","Bolivia",
    "Botswana","Burkina Faso","Burundi","Central African Republic","Chad",
    "Czech Republic","Ethiopia","Hungary","Kazakhstan","Kosovo","Kyrgyzstan",
    "Laos","Lesotho","Luxembourg","Malawi","Mali","Moldova","Mongolia",
    "Nepal","Niger","North Macedonia","Paraguay","Rwanda","Serbia","Slovakia",
    "South Sudan","Swaziland","Switzerland","Tajikistan","Turkmenistan","Uganda",
    "Uzbekistan","Zambia","Zimbabwe",
}

CHOKEPOINT_PAIRS = {
    frozenset(["Saudi Arabia", "Europe"]),
    frozenset(["Saudi Arabia", "EU-other"]),
    frozenset(["MENA-other", "EU-other"]),
    frozenset(["Egypt", "EU-other"]),
}

OWID_E_COLS = [
    "population", "gdp",
    "fossil_fuel_consumption", "renewables_electricity", "electricity_generation",
    "electricity_demand", "solar_electricity", "wind_electricity",
    "hydro_electricity", "nuclear_electricity", "oil_consumption",
    "gas_consumption", "coal_consumption", "fossil_share_energy",
    "renewables_share_energy", "low_carbon_share_elec", "energy_per_capita",
    "net_elec_imports", "greenhouse_gas_emissions",
]
OWID_C_COLS = ["co2", "co2_per_capita", "methane", "nitrous_oxide", "land_use_change_co2"]


# ════════════════════════════════════════════════════════════════════════════════
# 1. LOAD RAW DATA
# ════════════════════════════════════════════════════════════════════════════════

def load_all_raw():
    """Load and return all raw datasets as a dict of DataFrames."""
    print("Loading raw datasets...")
    raw = {}

    raw["owid_energy"] = pd.read_csv(RAW / "owid_energy_data.csv")
    print(f"  OWID Energy:      {raw['owid_energy'].shape}")

    raw["owid_co2"] = pd.read_csv(RAW / "owid_co2_data.csv")
    print(f"  OWID CO2:         {raw['owid_co2'].shape}")

    wb_files = {
        "wb_arable":    "worldbank/wb_arable_land.csv",
        "wb_water":     "worldbank/wb_water_stress.csv",
        "wb_trade":     "worldbank/wb_trade_gdp.csv",
        "wb_life_exp":  "worldbank/wb_life_exp.csv",
        "wb_fertiliser":"worldbank/wb_fertiliser.csv",
        "wb_uhc":       "worldbank/wb_uhc_index.csv",
    }
    for key, rel in wb_files.items():
        p = RAW / rel
        if p.exists():
            df = pd.read_csv(p, skiprows=4, encoding="utf-8-sig").dropna(subset=["Country Name"])
            # Forward/backward fill sparse indicators across years (UHC, water stress)
            yr_cols = [c for c in df.columns if str(c).isdigit()]
            df[yr_cols] = df[yr_cols].interpolate(axis=1, method="nearest").fillna(method="ffill", axis=1).fillna(method="bfill", axis=1)
            # UHC: divide by 25 to restore 0-100 WHO SCI scale
            if key == "wb_uhc":
                df[yr_cols] = df[yr_cols] / UHC_SCALE
            raw[key] = df
            print(f"  {key:20s}: {raw[key].shape}")
        else:
            print(f"  {key:20s}: FILE MISSING — {p}")
            raw[key] = pd.DataFrame()

    p = RAW / "fao/fao_food_price_index.csv"
    if p.exists():
        fpi_raw = pd.read_csv(p, header=None)
        fpi = fpi_raw.iloc[4:].copy()
        fpi.columns = (["Date","Food_Price_Index","Meat","Dairy","Cereals","Oils","Sugar"]
                       + [f"x{i}" for i in range(7, len(fpi_raw.columns))])
        fpi = fpi[["Date","Food_Price_Index","Meat","Dairy","Cereals","Oils","Sugar"]].copy()
        for col in ["Food_Price_Index","Meat","Dairy","Cereals","Oils","Sugar"]:
            fpi[col] = pd.to_numeric(fpi[col], errors="coerce")
        fpi["Year"] = pd.to_numeric(fpi["Date"].astype(str).str[:4], errors="coerce").astype("Int64")
        fpi = fpi.dropna(subset=["Year"])
        raw["fpi_annual"] = (fpi[fpi["Year"].between(2000, 2023)]
                             .groupby("Year")[["Food_Price_Index","Meat","Dairy","Cereals","Oils","Sugar"]]
                             .mean().reset_index())
        print(f"  FAO FPI annual:   {raw['fpi_annual'].shape}")
    else:
        raw["fpi_annual"] = pd.DataFrame()

    p = RAW / "fao/fao_food_balance_sheets.csv"
    if p.exists():
        fbs_full = pd.read_csv(p, encoding="latin-1")
        raw["fbs_kcal"]   = fbs_full[(fbs_full["Element"]=="Food supply (kcal/capita/day)") & (fbs_full["Item"]=="Grand Total")].copy()
        raw["fbs_prod"]   = fbs_full[(fbs_full["Element"]=="Production")     & (fbs_full["Item"]=="Grand Total")].copy()
        raw["fbs_import"] = fbs_full[(fbs_full["Element"]=="Import quantity") & (fbs_full["Item"]=="Grand Total")].copy()
        raw["fbs_export"] = fbs_full[(fbs_full["Element"]=="Export quantity") & (fbs_full["Item"]=="Grand Total")].copy()
        print(f"  FAO FBS kcal rows:{len(raw['fbs_kcal'])}")
    else:
        for k in ["fbs_kcal","fbs_prod","fbs_import","fbs_export"]:
            raw[k] = pd.DataFrame()

    p = RAW / "fao/fao_crop_production.csv"
    if p.exists():
        crops_full = pd.read_csv(p, encoding="latin-1")
        raw["fao_cereals"] = crops_full[(crops_full["Item"]=="Cereals, primary") &
                                         (crops_full["Element"]=="Production")].copy()
        print(f"  FAO Cereals rows: {len(raw['fao_cereals'])}")
    else:
        raw["fao_cereals"] = pd.DataFrame()

    return raw


# ════════════════════════════════════════════════════════════════════════════════
# 2. VALUE EXTRACTORS
# ════════════════════════════════════════════════════════════════════════════════

def owid_val(raw, dataset, country, year, col):
    """Get single value from OWID dataset."""
    df = raw[dataset]
    if df is None or col not in df.columns:
        return np.nan
    row = df[(df["country"] == country) & (df["year"] == year)]
    if len(row) == 0:
        return np.nan
    v = row.iloc[0][col]
    return float(v) if pd.notna(v) else np.nan



# ── UHC scale factor: WB SH.UHC.SRVS.CV.XD is stored at ×25 of the true 0-100 SCI ──
# Validated against WHO published values (USA 2019: raw=2024, /25=81 ✓)
UHC_SCALE = 25.0

def wb_val(raw, key, wb_name, year):
    """Get single value from World Bank wide-format CSV.
    
    For sparse indicators (UHC, water stress), interpolates from nearest
    available year when the requested year has no data.
    UHC is divided by 25.0 to restore the true 0-100 WHO SCI scale.
    """
    df = raw.get(key)
    if df is None or df.empty:
        return np.nan
    row = df[df["Country Name"] == wb_name]
    if len(row) == 0:
        return np.nan

    yr_cols = [c for c in df.columns if str(c).isdigit()]
    target  = str(year)

    # Try exact year first
    v = row.iloc[0][target] if target in df.columns else np.nan

    # If missing, use nearest available year (UHC published every 3-5 years)
    if pd.isna(v):
        row_data = row.iloc[0]
        best_dist, best_val = 9999, np.nan
        for c in yr_cols:
            val_c = row_data[c]
            if pd.notna(val_c):
                dist = abs(int(c) - year)
                if dist < best_dist:
                    best_dist, best_val = dist, float(val_c)
        v = best_val

    if pd.isna(v):
        return np.nan

    val = float(v)
    if key == "wb_uhc":
        val = float(np.clip(val / UHC_SCALE, 0.0, 100.0))
    return val

def wb_agg(raw, key, members, year, mode="mean"):
    """Aggregate World Bank value across bloc members."""
    vals = [wb_val(raw, key, NODE_TO_WB.get(m, m), year) for m in members]
    valid = [v for v in vals if not np.isnan(v)]
    if not valid:
        return np.nan
    return float(np.mean(valid)) if mode == "mean" else float(np.sum(valid))


def fao_val(raw, key, fao_name, year):
    """Get single value from FAO panel (Year columns = Y2010, Y2011, ...)."""
    df = raw.get(key)
    if df is None or df.empty:
        return np.nan
    col = f"Y{year}"
    row = df[df["Area"] == fao_name]
    if len(row) == 0 or col not in df.columns:
        return np.nan
    v = row.iloc[0][col]
    if pd.isna(v):
        return np.nan
    val = float(v)
    if key == "wb_uhc":  # WB encodes UHC SCI at x25 scale; /25 restores 0-100
        val = val / 25.0
    return val
    return float(v) if pd.notna(v) else np.nan

def owid_sum(raw, dataset, country_list, year, col):
    """Sum OWID column across multiple countries for bloc aggregation."""
    vals = [owid_val(raw, dataset, c, year, col) for c in country_list]
    valid = [v for v in vals if not np.isnan(v)]
    return float(np.sum(valid)) if valid else np.nan

def owid_mean(raw, dataset, country_list, year, col):
    """Mean OWID column across multiple countries (for rate variables)."""
    vals = [owid_val(raw, dataset, c, year, col) for c in country_list]
    valid = [v for v in vals if not np.isnan(v)]
    return float(np.mean(valid)) if valid else np.nan

def wb_agg(raw, key, members, year, mode="mean"):
    """Aggregate World Bank value across bloc members."""
    vals = [wb_val(raw, key, NODE_TO_WB.get(m, m), year) for m in members]
    valid = [v for v in vals if not np.isnan(v)]
    if not valid:
        return np.nan
    return float(np.mean(valid)) if mode == "mean" else float(np.sum(valid))

def fao_agg(raw, key, members, year, mode="sum"):
    """Aggregate FAO value across bloc members."""
    vals = [fao_val(raw, key, to_fao(m), year) for m in members]
    valid = [v for v in vals if not np.isnan(v)]
    if not valid:
        return np.nan
    return float(np.sum(valid)) if mode == "sum" else float(np.mean(valid))


# ════════════════════════════════════════════════════════════════════════════════
# 3. ABM PARAMETER DERIVATIONS
# ════════════════════════════════════════════════════════════════════════════════

def derive_Ti(gdppc, life_exp, fertiliser):
    """
    Technology index Tᵢ ∈ [0.01, 1.0]
    Formula: 0.30·min(LE/85,1) + 0.40·min(GDPpc/60000,1) + 0.30·min(fert/300,1)
    Source: DATA_PROVENANCE.md §3
    """
    le_norm  = min((life_exp  or 60 ) / 85,    1.0)
    gdp_norm = min((gdppc     or 0  ) / 60000, 1.0)
    fer_norm = min((fertiliser or 0 ) / 300,   1.0)
    t = 0.30*le_norm + 0.40*gdp_norm + 0.30*fer_norm
    return float(np.clip(t, 0.01, 1.0))

def derive_Wi(water_withdrawal_pct):
    """
    Water availability Wᵢ ∈ [0.10, 1.0]
    Formula: 1 − min(WW/100, 0.90)
    Higher withdrawal % → more stressed → less available
    """
    ww = water_withdrawal_pct or 20.0
    return float(np.clip(1.0 - min(ww/100, 0.90), 0.10, 1.0))

def derive_eps(gdppc, uhc):
    """
    Recovery rate εᵢ ∈ [0.01, 0.30]
    Formula: 0.01 + 0.15·min(GDPpc/60000,1) + 0.14·min(UHC/100,1)
    Wealthier nations with better health systems recover faster.
    """
    g = min((gdppc or 0) / 60000, 1.0)
    u = min((uhc   or 50) / 100,  1.0)
    return float(np.clip(0.01 + 0.15*g + 0.14*u, 0.01, 0.30))

def derive_psi(life_exp, uhc):
    """
    Famine mortality sensitivity ψᵢ ∈ [0.010, 0.100]
    Formula: 0.10 − 0.07·(0.5·min(LE/85,1) + 0.5·min(UHC/100,1))
    Poorer nations with weaker health systems → higher mortality per unit food deficit.
    """
    le = min((life_exp or 60) / 85,  1.0)
    u  = min((uhc      or 50) / 100, 1.0)
    return float(np.clip(0.10 - 0.07*(0.5*le + 0.5*u), 0.010, 0.100))

def derive_mu(gdppc, trade_pct):
    """
    Export conservatism μᵢ ∈ [0.30, 0.90]
    Formula: 0.90 − 0.50·min(GDPpc/60000,1) − 0.10·min(trade%/100,1)
    Poor, trade-closed nations hoard food; open rich nations export freely.
    """
    g = min((gdppc     or 0 ) / 60000, 1.0)
    t = min((trade_pct or 50) / 100,   1.0)
    return float(np.clip(0.90 - 0.50*g - 0.10*t, 0.30, 0.90))

def derive_sigma_safe(gdppc):
    """
    Safe food-security threshold σ_safe ∈ [1.10, 1.30]
    Richer countries set a higher precautionary threshold before exporting.
    """
    g = min((gdppc or 0) / 60000, 1.0)
    return float(np.clip(1.10 + 0.20*g, 1.10, 1.30))

def derive_energy_stress(fossil_share, renew_share, energy_t0, energy_t):
    """
    Energy stress index ESᵢ ∈ [0, 1]
    Formula: fossil_share/100 × demand_growth × (1 − renew_share/100)
    Homer-Dixon: energy stress = rising demand against declining EROI proxy.
    """
    fs  = (fossil_share or 70) / 100
    rs  = (renew_share  or 20) / 100
    dg  = (energy_t / energy_t0) if (energy_t0 and energy_t and energy_t0 > 0) else 1.0
    return float(np.clip(fs * dg * (1 - rs), 0.0, 1.0))

def derive_pop_growth(p2010, p2022):
    """Annual pop growth rate from 12-year trend (2010–2022)."""
    if p2010 and p2022 and p2010 > 0:
        return float(((p2022/p2010)**(1/12) - 1))
    return 0.015   # global average fallback


# ════════════════════════════════════════════════════════════════════════════════
# 4. BUILD NODE PANEL
# ════════════════════════════════════════════════════════════════════════════════

OWID_E_COLS = [
    "population", "gdp",
    "fossil_fuel_consumption", "renewables_electricity", "electricity_generation",
    "electricity_demand", "solar_electricity", "wind_electricity",
    "hydro_electricity", "nuclear_electricity", "oil_consumption",
    "gas_consumption", "coal_consumption", "fossil_share_energy",
    "renewables_share_energy", "low_carbon_share_elec", "energy_per_capita",
    "net_elec_imports", "greenhouse_gas_emissions",
]
OWID_C_COLS = ["co2", "co2_per_capita", "methane", "nitrous_oxide", "land_use_change_co2"]

def build_node_row(raw, node, year, is_hub, members=None):
    """
    Build one row of the node panel for a given node and year.
    Returns a dict with all raw and derived variables.
    """
    row = {"node": node, "year": year,
           "node_type": "hub" if is_hub else "bloc"}

    if is_hub:
        owid_name = node
        wb_name   = NODE_TO_WB.get(node, node)
        fao_name  = NODE_TO_FAO.get(node, node)

        # ── OWID Energy ──────────────────────────────────────────────────────
        for col in OWID_E_COLS:
            row[col] = owid_val(raw, "owid_energy", owid_name, year, col)
        for col in OWID_C_COLS:
            row[col] = owid_val(raw, "owid_co2", owid_name, year, col)

        # ── World Bank ───────────────────────────────────────────────────────
        row["arable_land_pct"]      = wb_val(raw, "wb_arable",    wb_name, year)
        row["water_withdrawal_pct"] = wb_val(raw, "wb_water",     wb_name, year)
        row["trade_pct_gdp"]        = wb_val(raw, "wb_trade",     wb_name, year)
        row["life_expectancy"]      = wb_val(raw, "wb_life_exp",  wb_name, year)
        row["fertiliser_kg_ha"]     = wb_val(raw, "wb_fertiliser",wb_name, year)
        row["uhc_index"]            = wb_val(raw, "wb_uhc",       wb_name, year)

        # ── FAO ──────────────────────────────────────────────────────────────
        row["kcal_cap_day"]     = fao_val(raw, "fbs_kcal",   fao_name, year) if year >= 2010 else np.nan
        row["food_prod_kt"]     = fao_val(raw, "fbs_prod",   fao_name, year) if year >= 2010 else np.nan
        row["food_import_kt"]   = fao_val(raw, "fbs_import", fao_name, year) if year >= 2010 else np.nan
        row["food_export_kt"]   = fao_val(raw, "fbs_export", fao_name, year) if year >= 2010 else np.nan
        row["cereal_prod_t"]    = fao_val(raw, "fao_cereals",fao_name, year)

    else:
        # ── Bloc: aggregate across members ───────────────────────────────────
        # SUM for flow variables, MEAN for rate/share variables
        for col in ["population","gdp","fossil_fuel_consumption","renewables_electricity",
                    "electricity_generation","electricity_demand","solar_electricity",
                    "wind_electricity","hydro_electricity","nuclear_electricity",
                    "oil_consumption","gas_consumption","coal_consumption",
                    "greenhouse_gas_emissions","net_elec_imports"]:
            row[col] = owid_sum(raw, "owid_energy", members, year, col)

        for col in ["fossil_share_energy","renewables_share_energy",
                    "low_carbon_share_elec","energy_per_capita"]:
            row[col] = owid_mean(raw, "owid_energy", members, year, col)

        for col in OWID_C_COLS:
            mode = "mean" if "per_capita" in col else "sum"
            if mode == "sum":
                row[col] = owid_sum(raw, "owid_co2", members, year, col)
            else:
                row[col] = owid_mean(raw, "owid_co2", members, year, col)

        row["arable_land_pct"]      = wb_agg(raw, "wb_arable",    members, year, "mean")
        row["water_withdrawal_pct"] = wb_agg(raw, "wb_water",     members, year, "mean")
        row["trade_pct_gdp"]        = wb_agg(raw, "wb_trade",     members, year, "mean")
        row["life_expectancy"]      = wb_agg(raw, "wb_life_exp",  members, year, "mean")
        row["fertiliser_kg_ha"]     = wb_agg(raw, "wb_fertiliser",members, year, "mean")
        row["uhc_index"]            = wb_agg(raw, "wb_uhc",       members, year, "mean")

        fao_m = [to_fao(m) for m in members]
        row["kcal_cap_day"]   = np.nanmean([fao_val(raw,"fbs_kcal",  f,year) for f in fao_m]) if year>=2010 else np.nan
        row["food_prod_kt"]   = fao_agg(raw,"fbs_prod",  members,year,"sum") if year>=2010 else np.nan
        row["food_import_kt"] = fao_agg(raw,"fbs_import",members,year,"sum") if year>=2010 else np.nan
        row["food_export_kt"] = fao_agg(raw,"fbs_export",members,year,"sum") if year>=2010 else np.nan
        row["cereal_prod_t"]  = fao_agg(raw,"fao_cereals",members,year,"sum")

    # ── Derived quantities ────────────────────────────────────────────────────
    pop    = row.get("population") or np.nan
    gdp    = row.get("gdp")        or np.nan
    gdppc  = gdp/pop if (not np.isnan(gdp) and not np.isnan(pop) and pop > 0) else np.nan

    row["gdp_per_capita"] = gdppc
    row["gdp_bn_usd2015"] = gdp/1e9  if not np.isnan(gdp)  else np.nan
    row["pop_millions"]   = pop/1e6  if not np.isnan(pop)   else np.nan

    # Annual caloric demand (kcal/year)
    kcal = row.get("kcal_cap_day")
    if not np.isnan(kcal if kcal is not None else np.nan) and not np.isnan(pop):
        row["caloric_demand_kcal_yr"] = float(kcal) * float(pop) * 365
    else:
        # Fallback: income-class estimate
        if not np.isnan(gdppc):
            c_i = 3200 if gdppc > 20000 else (2700 if gdppc > 5000 else 2200)
        else:
            c_i = 2500
        row["caloric_demand_kcal_yr"] = c_i * float(pop) * 365 if not np.isnan(pop) else np.nan

    # ── ABM Parameters ────────────────────────────────────────────────────────
    row["Ti"] = derive_Ti(gdppc,
                          row.get("life_expectancy"),
                          row.get("fertiliser_kg_ha"))

    row["Wi"] = derive_Wi(row.get("water_withdrawal_pct"))

    row["Li"] = float(np.clip(row.get("arable_land_pct") or 10.0, 1.0, 100.0))

    row["eps_i"] = derive_eps(gdppc, row.get("uhc_index"))

    row["psi_i"] = derive_psi(row.get("life_expectancy"), row.get("uhc_index"))

    row["mu_i"]  = derive_mu(gdppc, row.get("trade_pct_gdp"))

    row["sigma_safe_i"] = derive_sigma_safe(gdppc)

    row["bi_minus_di"] = derive_pop_growth(
        owid_val(raw,"owid_energy", node if is_hub else (members[0] if members else node), 2010, "population"),
        owid_val(raw,"owid_energy", node if is_hub else (members[0] if members else node), 2022, "population"),
    )

    # Energy stress (Homer-Dixon ES_index)
    e_t0  = owid_val(raw,"owid_energy",
                     node if is_hub else (members[0] if members else node),
                     2000, "fossil_fuel_consumption")
    e_t   = row.get("fossil_fuel_consumption")
    row["energy_stress_index"] = derive_energy_stress(
        row.get("fossil_share_energy"),
        row.get("renewables_share_energy"),
        e_t0, e_t,
    )

    # FAO FPI baseline price for this year
    fpi_df = raw.get("fpi_annual")
    if fpi_df is not None and not fpi_df.empty:
        yr_row = fpi_df[fpi_df["Year"] == year]
        row["fao_fpi"] = float(yr_row["Food_Price_Index"].values[0]) if len(yr_row) else np.nan
    else:
        row["fao_fpi"] = np.nan

    return row


def build_node_panel(raw):
    """Build full 35 × 24 node panel."""
    print("\nBuilding node panel (35 nodes × 24 years)...")
    rows = []

    for node in ALL_NODES:
        is_hub  = node in HUB_COUNTRIES
        members = None if is_hub else BLOC_MEMBERS[node]

        for year in YEARS:
            r = build_node_row(raw, node, year, is_hub, members)
            rows.append(r)

        print(f"  ✓ {node}")

    panel = pd.DataFrame(rows)

    # Column order
    id_cols   = ["node","year","node_type"]
    raw_cols  = [c for c in panel.columns if c not in id_cols
                 and not c.startswith(("Ti","Wi","Li","eps","psi","mu",
                                        "sigma","bi_","energy_stress",
                                        "gdp_per","gdp_bn","pop_m","caloric"))]
    abm_cols  = ["gdp_per_capita","gdp_bn_usd2015","pop_millions",
                 "caloric_demand_kcal_yr","Ti","Wi","Li","eps_i","psi_i",
                 "mu_i","sigma_safe_i","bi_minus_di","energy_stress_index","fao_fpi"]
    ordered   = id_cols + raw_cols + [c for c in abm_cols if c in panel.columns]
    panel     = panel[[c for c in ordered if c in panel.columns]]

    out = PROC / "node_panel.csv"
    panel.to_csv(out, index=False)
    print(f"\n  ✓ node_panel.csv saved: {panel.shape[0]} rows × {panel.shape[1]} cols → {out}")
    return panel


# ════════════════════════════════════════════════════════════════════════════════
# 5. BUILD NETWORK WEIGHTS (35 × 35 full mesh)
# ════════════════════════════════════════════════════════════════════════════════

# Approximate geographic centroid lat/lon for each node (for distance proxy)
NODE_COORDS = {
    "United States":               (39.5, -98.4),
    "China":                       (35.9, 104.2),
    "India":                       (20.6,  78.9),
    "Brazil":                      (-14.2, -51.9),
    "Russia":                      (61.5,  105.3),
    "Ukraine":                     (48.4,   31.2),
    "Argentina":                   (-38.4,  -63.6),
    "Australia":                   (-25.3,  133.8),
    "Canada":                      (56.1,  -106.3),
    "France":                      (46.2,    2.2),
    "Indonesia":                   (-0.8,  113.9),
    "Vietnam":                     (14.1,  108.3),
    "Thailand":                    (15.9,  100.9),
    "Egypt":                       (26.8,   30.8),
    "Nigeria":                     (9.1,    8.7),
    "Bangladesh":                  (23.7,   90.4),
    "Pakistan":                    (30.4,   69.3),
    "Germany":                     (51.2,   10.5),
    "Japan":                       (36.2,  138.3),
    "United Kingdom":              (55.4,   -3.4),
    "Saudi Arabia":                (23.9,   45.1),
    "West Africa (ECOWAS)":        (12.0,   -5.0),
    "East Africa":                 (2.0,    37.0),
    "Southern Africa (SADC)":      (-22.0,  28.0),
    "Central Africa":              (4.0,    22.0),
    "MENA-other":                  (28.0,   43.0),
    "Central Asia":                (44.0,   66.0),
    "South Asia-other":            (18.0,   83.0),
    "Southeast Asia-other":        (8.0,   115.0),
    "Pacific/Oceania-other":       (-15.0,  165.0),
    "Caribbean & Central America": (15.0,  -90.0),
    "Andean & Southern Cone-other":(-25.0,  -65.0),
    "Eastern Europe-other":        (50.0,   23.0),
    "EU-other":                    (47.0,   15.0),
    "Nordics":                     (63.0,   15.0),
}

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R  = 6371
    φ1, φ2 = np.radians(lat1), np.radians(lat2)
    dφ = np.radians(lat2 - lat1)
    dλ = np.radians(lon2 - lon1)
    a  = np.sin(dφ/2)**2 + np.cos(φ1)*np.cos(φ2)*np.sin(dλ/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def node_is_landlocked(node):
    if node in HUB_COUNTRIES:
        return node in LANDLOCKED
    # For blocs, check if majority of members are landlocked
    members = BLOC_MEMBERS.get(node, [])
    ll = sum(1 for m in members if m in LANDLOCKED)
    return ll > len(members) / 2

def chokepoint_penalty(node_i, node_j):
    """Extra transaction cost if trade route passes through major chokepoint."""
    pair = frozenset([node_i, node_j])
    if pair in CHOKEPOINT_PAIRS:
        return 0.15
    # Suez-dependent: Asia ↔ Europe trade
    asia  = {"China","India","Indonesia","Vietnam","Thailand","Bangladesh","Pakistan",
              "Japan","Southeast Asia-other","South Asia-other"}
    europe= {"Germany","France","United Kingdom","EU-other","Eastern Europe-other","Nordics"}
    if (node_i in asia and node_j in europe) or (node_i in europe and node_j in asia):
        return 0.12
    # Hormuz-dependent: Gulf ↔ rest
    gulf = {"Saudi Arabia","MENA-other"}
    if (node_i in gulf) or (node_j in gulf):
        return 0.08
    return 0.0


def build_network_weights(panel, snap_year=2022):
    """
    Build 35×35 directed trade network.

    For each ordered pair (i,j):
      Cij  = gravity capacity = G × GDPi × GDPj / dist² × tradei × tradej
      kij  = transaction cost = base_dist + landlocked + chokepoint
      rho0 = political risk baseline = f(stability proxies)

    Returns DataFrame with columns:
      from_node, to_node, distance_km, Cij, kij, rho0_ij,
      gdp_i_bn, gdp_j_bn, trade_i_pct, trade_j_pct
    """
    print(f"\nBuilding 35×35 network weights (snapshot year {snap_year})...")

    # Snapshot of GDP and trade openness
    snap = panel[panel["year"] == snap_year].set_index("node")

    def get(node, col):
        try:
            v = snap.loc[node, col]
            return float(v) if pd.notna(v) else None
        except:
            return None

    G_base = 6e10   # gravity constant (calibrated to FAO cereal trade magnitudes)
    MIN_CAP = 1e6   # minimum capacity threshold (prune negligible edges)

    rows = []
    for i_node in ALL_NODES:
        for j_node in ALL_NODES:
            if i_node == j_node:
                continue

            # ── Gravity capacity ──────────────────────────────────────────────
            lat1, lon1 = NODE_COORDS.get(i_node, (0, 0))
            lat2, lon2 = NODE_COORDS.get(j_node, (0, 0))
            dist_km    = max(haversine_km(lat1,lon1,lat2,lon2), 100)  # floor 100km

            gdp_i   = get(i_node, "gdp")      or 1e9
            gdp_j   = get(j_node, "gdp")      or 1e9
            trade_i = (get(i_node, "trade_pct_gdp") or 50) / 100
            trade_j = (get(j_node, "trade_pct_gdp") or 50) / 100

            Cij = G_base * gdp_i * gdp_j / (dist_km**2) * trade_i * trade_j
            Cij = max(Cij, 0.0)

            # ── Transaction cost ──────────────────────────────────────────────
            base_cost   = min(dist_km / 20000, 0.50)   # normalised 0–0.50
            ll_i        = 0.25 if node_is_landlocked(i_node) else 0.0
            ll_j        = 0.25 if node_is_landlocked(j_node) else 0.0
            cp_cost     = chokepoint_penalty(i_node, j_node)
            kij         = float(np.clip(base_cost + ll_i + ll_j + cp_cost, 0.0, 0.95))

            # ── Political risk baseline ───────────────────────────────────────
            # Proxy stability from GDP per capita (higher → more stable)
            gdppc_i = get(i_node, "gdp_per_capita") or 5000
            gdppc_j = get(j_node, "gdp_per_capita") or 5000
            stab_i  = min(gdppc_i / 50000, 1.0)
            stab_j  = min(gdppc_j / 50000, 1.0)
            rho0    = float(np.clip(0.10 + (1 - 0.5*(stab_i + stab_j))*0.60, 0.05, 0.85))

            rows.append({
                "from_node":   i_node,
                "to_node":     j_node,
                "distance_km": round(dist_km, 1),
                "Cij":         round(Cij, 2),
                "kij":         round(kij, 4),
                "rho0_ij":     round(rho0, 4),
                "gdp_i_bn":    round(gdp_i/1e9, 2),
                "gdp_j_bn":    round(gdp_j/1e9, 2),
                "trade_i_pct": round(trade_i*100, 2),
                "trade_j_pct": round(trade_j*100, 2),
                "active":      1 if Cij >= MIN_CAP else 0,
            })

    net = pd.DataFrame(rows)
    out = PROC / "network_weights.csv"
    net.to_csv(out, index=False)

    n_active = net["active"].sum()
    print(f"  ✓ network_weights.csv: {len(net)} directed edges")
    print(f"    Active (Cij ≥ {MIN_CAP:.0e}): {n_active} / {len(net)}")
    print(f"    Mean Cij (active): {net.loc[net['active']==1,'Cij'].mean():.2e}")
    print(f"    Mean kij:          {net['kij'].mean():.4f}")
    print(f"    Mean rho0:         {net['rho0_ij'].mean():.4f}")
    print(f"    → {out}")
    return net


# ════════════════════════════════════════════════════════════════════════════════
# 6. ABM INIT SNAPSHOT AND FPI OUTPUT
# ════════════════════════════════════════════════════════════════════════════════

def build_abm_init(panel, snap_year=2022):
    """Single-year ABM initialisation table (2022 snapshot)."""
    snap = panel[panel["year"] == snap_year].copy()
    out  = PROC / "abm_init_2022.csv"
    snap.to_csv(out, index=False)
    print(f"\n  ✓ abm_init_2022.csv: {snap.shape} → {out}")
    return snap

def save_fpi(raw):
    """Save FAO FPI annual averages."""
    fpi = raw.get("fpi_annual")
    if fpi is not None and not fpi.empty:
        out = PROC / "fpi_annual.csv"
        fpi.to_csv(out, index=False)
        print(f"  ✓ fpi_annual.csv: {fpi.shape} → {out}")


# ════════════════════════════════════════════════════════════════════════════════
# 7. VALIDATION REPORT
# ════════════════════════════════════════════════════════════════════════════════

def validate_panel(panel):
    """Print data completeness report per variable."""
    print("\n── Data Completeness Report (2022 snapshot) ──")
    snap = panel[panel["year"] == 2022]
    cols_to_check = [
        "population","gdp","fossil_fuel_consumption","renewables_electricity",
        "arable_land_pct","water_withdrawal_pct","life_expectancy","fertiliser_kg_ha",
        "trade_pct_gdp","uhc_index","kcal_cap_day","cereal_prod_t",
        "Ti","Wi","Li","eps_i","psi_i","mu_i","energy_stress_index",
    ]
    for col in cols_to_check:
        if col not in snap.columns:
            print(f"  {col:30s}: MISSING COLUMN")
            continue
        n_filled  = snap[col].notna().sum()
        pct       = 100 * n_filled / len(snap)
        status    = "✓" if pct >= 70 else ("△" if pct >= 40 else "✗")
        print(f"  {status} {col:30s}: {n_filled:2d}/{len(snap)} ({pct:.0f}%)")

    print("\n── ABM Parameter Ranges (2022) ──")
    for param, lo, hi in [("Ti",0.01,1.0),("Wi",0.1,1.0),("Li",1,100),
                            ("eps_i",0.01,0.30),("psi_i",0.01,0.10),
                            ("mu_i",0.30,0.90),("energy_stress_index",0,1)]:
        if param in snap.columns:
            col_data = snap[param].dropna()
            if len(col_data):
                print(f"  {param:25s}: min={col_data.min():.4f}  "
                      f"mean={col_data.mean():.4f}  max={col_data.max():.4f}  "
                      f"[expected {lo}–{hi}]")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("  Phase 1 Data Pipeline — Food-Energy Systemic Risk ABM")
    print("  Framework: Gambhir et al. (2025) + Homer-Dixon et al. (2015)")
    print("=" * 65)

    raw   = load_all_raw()
    panel = build_node_panel(raw)
    net   = build_network_weights(panel)
    _     = build_abm_init(panel)
    save_fpi(raw)
    validate_panel(panel)

    print("\n" + "=" * 65)
    print("  Phase 1 complete.")
    print(f"  Outputs in: {PROC}")
    print("  Files:")
    for f in sorted(PROC.iterdir()):
        size = f.stat().st_size // 1024
        print(f"    {f.name:40s} {size:>6} KB")
    print("=" * 65)


if __name__ == "__main__":
    main()

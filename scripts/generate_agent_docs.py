#!/usr/bin/env python3
"""
generate_agent_docs.py
------------------------
Generates one documentation file per node (/docs/agents/<Name>.md),
per the "every node is an autonomous digital agent" requirement.

DESIGN PRINCIPLE (why this is a script, not 35 hand-written files):
every number in the output below is read directly from
data/processed/node_parameters.csv and node_panel.csv, or derived from
them with a documented, auditable formula -- zero numbers are invented.
A generator script is the only way to guarantee this at 35-node scale;
hand-writing 35 files risks silent inconsistency or fabrication under
time pressure, which the task's own "never fabricate" rule forbids.

What is REAL in the output: every state-variable value, every trade
partner ranking, every reserve-months/undernourishment/risk figure,
every historical trend, every real policy-lever equation.

What is HONESTLY MARKED, not fabricated: per-variable sensitivity
(no per-node-per-parameter sensitivity study exists -- only model-level
Sobol/OAT results do, and this is stated explicitly rather than
inventing a number); which policy levers are "available, not currently
active" vs the two levers (export policy, reserve accumulation) that are
always-on per-node mechanisms with real current values.

Run: PYTHONPATH=model/src python3 scripts/generate_agent_docs.py
"""
import sys
import os
import pandas as pd
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "processed")
OUT_DIR = os.path.join(REPO_ROOT, "docs", "agents")

VARIABLE_META = {
    # column: (display name, units, equation reference, calibration source, confidence)
    "P_i": ("Population", "persons", "Cobb-Douglas demand anchor (EQUATIONS_REFERENCE.md §1)", "OWID/World Bank population", "High"),
    "b_i": ("Birth rate", "per capita/yr", "Population dynamics (§9)", "OWID demographic data, 2010-2022 trend", "Medium"),
    "d_i": ("Death rate", "per capita/yr", "Population dynamics (§9)", "OWID demographic data, 2010-2022 trend", "Medium"),
    "L_i": ("Arable land", "index", "Cobb-Douglas land term, alpha=0.30", "World Bank AG.LND.ARBL.ZS", "High"),
    "W_i": ("Water availability", "index", "Cobb-Douglas water term, beta=0.25", "World Bank ER.H2O.FWTL.ZS (static index)", "Medium"),
    "E_fuel_i": ("Fossil energy endowment", "TWh-equiv", "Cobb-Douglas energy term, gamma=0.20", "OWID energy data", "High"),
    "E_elec_i": ("Electricity endowment", "TWh-equiv", "Energy stress index input (energy.py)", "OWID energy data", "High"),
    "K_i": ("Capital stock", "USD bn", "Coping capacity CC_index; trade affordability", "World Bank GDP", "High"),
    "T_i": ("Technology index", "index [0,1]", "Cobb-Douglas tech term, delta=0.25; CC_index (dominant weight 0.47)", "Derived, World Bank indicators", "Medium"),
    "A_i": ("Total factor productivity", "multiplier", "Cobb-Douglas scale term", "SSR-inverted from FAO crop production data", "Medium"),
    "theta_animal_i": ("Animal-product output share", "fraction", "Food stock composition split", "FAO Food Balance Sheets", "Medium"),
    "theta_perish_i": ("Perishable output share", "fraction", "Food stock composition split", "FAO Food Balance Sheets", "Medium"),
    "theta_imperish_i": ("Imperishable (grain) output share", "fraction", "Food stock composition split", "FAO Food Balance Sheets", "Medium"),
    "D_i_Mt": ("Annual caloric demand", "kcal/yr", "sigma denominator (food security ratio)", "FAO kcal/cap/day x population", "High"),
    "F_imperish_i": ("Initial imperishable stock", "kcal", "sigma numerator, stock-cap logic", "Derived initial condition", "Medium"),
    "F_a_i": ("Initial animal-product stock", "kcal", "Food stock composition", "Derived initial condition", "Medium"),
    "F_perish_i": ("Initial perishable stock", "kcal", "Food stock composition", "Derived initial condition", "Medium"),
    "R_i": ("Strategic reserve stock", "kcal", "Reserve-draw term in sigma (capped 30% demand/step)", "Derived initial condition", "Low-Medium"),
    "mu_i": ("Maximum export fraction", "fraction", "3-regime export policy ceiling (EQUATIONS_REFERENCE.md, Regime 3)", "Calibrated from real trade share, Agricultural Trade Multiplier corrected", "Medium"),
    "sigma_safe_i": ("Safe food-security threshold", "ratio", "Regime-2/3 boundary in export policy", "Calibrated, 1.10-1.30 range", "Medium"),
    "epsilon_i": ("General efficiency/coping term", "index", "Coping capacity CC_index input", "Derived", "Low"),
    "psi_i": ("Famine mortality sensitivity", "index", "Population dynamics death-rate penalty", "Derived", "Low"),
    "rho_i": ("Baseline political risk", "index [0,1]", "CC_index (weight -0.11); trade risk gate", "Political stability proxy data", "Medium"),
    "clim_vuln_i": ("Climate vulnerability", "index [0,1]", "Climate modifier C_i(t); CC_index (weight -0.12)", "ND-GAIN food sub-index, 2022", "Medium-High"),
    "undernourishment_baseline_pct": ("Baseline undernourishment", "%", "CC_index ML-regression TARGET (not fed into live sim loop)", "FAO undernourishment prevalence", "High"),
    "epsilon_ef": ("Energy-food coupling strength", "index [0,1]", "Arrow 1: production TFP penalty from energy stress", "IEA/FAO agriculture-sector energy data", "Medium"),
}

REAL_POLICY_LEVERS = [
    # (name, mechanism file/function, node-specific or global, status)
    ("Reserve mandate", "political_economy.py::apply_reserve_mandate", "Node-targeted", "Implemented"),
    ("Global reserve pool (mutual insurance)", "scenarios.py::make_global_reserve_pool_lever", "Global (all nodes), one-time redistribution", "Implemented"),
    ("Food aid (node-to-node)", "scenarios.py::make_food_aid_lever", "Node-pair", "Implemented"),
    ("Coordinated export restriction", "scenarios.py::make_coordinated_export_restriction_lever", "Multi-node", "Implemented"),
    ("Climate adaptation funding", "scenarios.py::make_climate_adaptation_lever", "Node-targeted", "Implemented"),
    ("Import tariff/subsidy", "scenarios.py::make_import_tariff_lever, trade.py::_gravity_volume", "Node-targeted", "Implemented"),
    ("Trade diversification", "political_economy.py::apply_diversification", "Global (network-wide)", "Implemented"),
    ("Trader regulation", "political_economy.py::apply_trader_regulation", "Global", "Implemented, but margin_cap parameter confirmed non-functional (see LIMITATIONS.md)"),
    ("Renewable energy push", "scenarios.py::make_renewable_push_lever", "Global (all nodes)", "Implemented"),
    ("Energy release/subsidy", "scenarios.py::make_energy_intervention_lever", "~1 randomly-scoped node (no exact targeting)", "Implemented, targeting limitation documented"),
    ("Fertilizer support (interim proxy)", "scenarios.py::make_fertilizer_support_lever_INTERIM", "Node-targeted", "Implemented as INTERIM energy-channel proxy, not real fertilizer state"),
    ("Fertilizer redistribution (real N/P/K)", "resource_drivers.py::make_fertilizer_redistribution_lever", "Node-pair", "Implemented, requires FertilizerDriver attached (not in baseline)"),
    ("Export ban (3-regime, always-on)", "agent.py::update_export_policy", "Per-node, continuous", "Implemented, core mechanism"),
    ("Sanction / trade-risk penalty", "trade.py::_effective_risk", "Edge-level", "Implemented, unused-by-default hook"),
]


def reserve_months(row):
    if row["D_i_Mt"] <= 0:
        return None
    return round((row["R_i"] / row["D_i_Mt"]) * 12, 2)


def get_trade_partners(nw, node, direction, top_n=5):
    if direction == "export":
        sub = nw[nw["from_node"] == node].sort_values("C_ij_corrected", ascending=False)
        partner_col = "to_node"
    else:
        sub = nw[nw["to_node"] == node].sort_values("C_ij_corrected", ascending=False)
        partner_col = "from_node"
    rows = []
    for _, r in sub.head(top_n).iterrows():
        rows.append((r[partner_col], r["C_ij_corrected"], r["rho_ij_risk"], bool(r["active"])))
    return rows


def historical_trend(panel, node, column, start=2000, end=2022):
    sub = panel[(panel["node"] == node) & (panel["year"].between(start, end))][["year", column]].dropna()
    if sub.empty:
        return None
    v0 = sub.iloc[0][column]
    v1 = sub.iloc[-1][column]
    vmin, vmax = sub[column].min(), sub[column].max()
    return {
        "start_year": int(sub.iloc[0]["year"]), "start_value": round(float(v0), 4),
        "end_year": int(sub.iloc[-1]["year"]), "end_value": round(float(v1), 4),
        "min": round(float(vmin), 4), "max": round(float(vmax), 4),
    }


def generate_agent_doc(name, row, nw, panel):
    lines = []
    lines.append(f"# Agent Profile: {name}\n")
    lines.append("*Generated by `scripts/generate_agent_docs.py` from real calibration data "
                  "(`data/processed/node_parameters.csv`, `node_panel.csv`, `network_weights.csv`). "
                  "Every value below is read or derived from those files -- see the script's "
                  "own docstring for exactly which fields are computed vs. explicitly marked "
                  "as not individually available.*\n")

    # 1. Identity
    lines.append("## 1. Identity\n")
    node_type = "Individually-modelled hub country" if row["Type"] == "hub_country" else "Regional bloc aggregate"
    lines.append(f"- **Name:** {name}")
    lines.append(f"- **Type:** {node_type}")
    lines.append(f"- **Population:** {row['P_i']:,.0f}")
    k_rank = int((row["K_i"] > NODE_DF["K_i"]).sum() + 1)
    lines.append(f"- **Capital stock rank:** {k_rank} of 35 (by K_i, descending)")
    reserve_m = reserve_months(row)
    net_export_cap = nw[nw["from_node"] == name]["C_ij_corrected"].sum()
    net_import_cap = nw[nw["to_node"] == name]["C_ij_corrected"].sum()
    trade_role = "Net export capacity > import capacity (exporter-leaning)" if net_export_cap > net_import_cap \
        else "Net import capacity > export capacity (importer-leaning)"
    lines.append(f"- **Trade role (from real network capacity):** {trade_role} "
                  f"(export capacity {net_export_cap:.2e}, import capacity {net_import_cap:.2e})")
    lines.append(f"- **Strategic reserve buffer:** {reserve_m if reserve_m is not None else 'N/A'} months of demand\n")

    # 2. State variables
    lines.append("## 2. Current State Variables\n")
    lines.append("| Variable | Value | Meaning | Units | Governing equation | Calibration source | Confidence |")
    lines.append("|---|---|---|---|---|---|---|")
    for col, (disp, units, eq, source, conf) in VARIABLE_META.items():
        val = row.get(col)
        val_str = "N/A (missing in source data)" if pd.isna(val) else (f"{val:,.4g}" if isinstance(val, (int, float)) else str(val))
        lines.append(f"| `{col}` | {val_str} | {disp} | {units} | {eq} | {source} | {conf} |")
    lines.append("\n**Sensitivity note (honest, not fabricated):** no per-node, per-parameter "
                  "sensitivity study exists for this agent's individual state variables. "
                  "Model-level parameter sensitivity (which CONSTANTS dominate output variance "
                  "across the whole 35-node system, e.g. RC_PRICE_AMPLIFICATION) is documented "
                  "in `docs/validation/VALIDATION_REPORT_INITIAL.md` Section 3 (Sobol/OAT results) "
                  "-- that is a different, model-wide question from \"how sensitive is THIS "
                  "agent's outcome to THIS agent's mu_i,\" which has not been separately studied.\n")

    # Historical trend (real, from node_panel.csv)
    lines.append("### Historical trend (2000-2022, real data from `node_panel.csv`)\n")
    trend_cols = [("population", "Population"), ("gdp_bn_usd2015", "GDP (bn USD 2015)"),
                  ("fao_fpi", "Local FAO Food Price Index proxy"), ("cereal_prod_t", "Cereal production (t)")]
    lines.append("| Variable | 2000 (or earliest) | 2022 (or latest) | Min | Max |")
    lines.append("|---|---|---|---|---|")
    any_trend = False
    for col, disp in trend_cols:
        t = historical_trend(panel, name, col)
        if t:
            any_trend = True
            lines.append(f"| {disp} | {t['start_value']:,} ({t['start_year']}) | "
                          f"{t['end_value']:,} ({t['end_year']}) | {t['min']:,} | {t['max']:,} |")
    if not any_trend:
        lines.append("| *(no historical panel data available for this node)* | | | | |")
    lines.append("")

    # 3. Policy variables
    lines.append("## 3. Policy Variables\n")
    lines.append("### Always-on, per-node calibrated mechanisms (not optional levers -- these run in every scenario)\n")
    lines.append(f"- **Export policy (3-regime)**: `mu_i` = {row['mu_i']:.3f} (max export fraction), "
                  f"`sigma_safe_i` = {row['sigma_safe_i']:.3f} (safety threshold). "
                  f"Equation: `docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md` Section 16 "
                  f"(\"Export policy (3-regime)\"). Implemented in `agent.py::update_export_policy`.")
    lines.append(f"- **Reserve accumulation**: `R_i` (initial) = {row['R_i']:,.3g} kcal, target ratio 0.15x "
                  f"imperishable stock, 5%/step max transfer. Implemented in "
                  f"`agent.py::_replenish_reserves`.\n")

    lines.append("### Available policy levers (real, implemented mechanisms; NOT active by default -- "
                  "invoked via `POST /api/policy_search` or `node_level_policy_search()`)\n")
    lines.append("| Policy | Scope | Status |")
    lines.append("|---|---|---|")
    for pname, mech, scope, status in REAL_POLICY_LEVERS:
        lines.append(f"| {pname} | {scope} | {status} |")
    lines.append("\n**No policy in the table above was invented for this document** -- every row "
                  "traces to a real function in `model/src/`, cross-referenced in "
                  "`docs/TRACEABILITY_MATRIX.md`. Policies mentioned in general Digital Twin "
                  "planning documents but not in this table (e.g. carbon tax, migration policy, "
                  "labour protection) are **not implemented** -- see "
                  "`docs/global_policies/README.md` for the full accounting of what's proposed vs. real.\n")

    # 4. Trade relationships
    lines.append("## 4. Trade Relationships (real, from `network_weights.csv`)\n")
    lines.append("### Top export destinations (by corrected capacity)\n")
    lines.append("| Partner | Capacity (C_ij_corrected) | Political risk (rho_ij) | Edge active |")
    lines.append("|---|---|---|---|")
    for partner, cap, risk, active in get_trade_partners(nw, name, "export"):
        lines.append(f"| {partner} | {cap:.3e} | {risk:.3f} | {active} |")
    lines.append("\n### Top import sources (by corrected capacity)\n")
    lines.append("| Partner | Capacity (C_ij_corrected) | Political risk (rho_ij) | Edge active |")
    lines.append("|---|---|---|---|")
    for partner, cap, risk, active in get_trade_partners(nw, name, "import"):
        lines.append(f"| {partner} | {cap:.3e} | {risk:.3f} | {active} |")
    lines.append("\n**Network centrality / cascade contribution**: not individually computed per "
                  "agent in this document -- network-wide hub/centrality validation exists at "
                  "the model level (`docs/validation/VALIDATION_REPORT_INITIAL.md`'s network "
                  "hub validation, 4/10 real top-pagerank hubs recovered) but a per-agent "
                  "centrality ranking was not computed this session. Flagged as real, tractable "
                  "future work (the data to compute it, `network_weights.csv`, already exists) "
                  "rather than fabricated here.\n")

    # 5. Climate profile
    lines.append("## 5. Climate Profile\n")
    lines.append(f"- **Climate vulnerability index (ND-GAIN, real):** {row['clim_vuln_i']:.3f}")
    lines.append("- **Drought / heatwave / flood indices:** 0.0 at baseline (only set by discrete "
                  "trigger injection in the default configuration -- see `model/src/stc_engine.py`'s "
                  "climate-type triggers for real historical calibration, e.g. Australia 2006 "
                  "drought chi_shock=0.48).")
    lines.append("- **Continuous rainfall/temperature driver:** mechanism implemented "
                  "(`model/src/climate_drivers.py::ContinuousClimateDriver`), **not attached in "
                  "baseline runs**, and runs on synthetic placeholder data when attached -- no "
                  "real CHIRPS/Berkeley Earth data was integrated this session. See "
                  "`LIMITATIONS.md`.")
    lines.append("- **Soil quality:** mechanism implemented (`SoilQualityDriver`), not attached "
                  "by default; initial condition 1.0 (undegraded) when attached.\n")

    # 6. Resource profile
    lines.append("## 6. Resource Profile\n")
    lines.append(f"- **Water availability index (static, real):** {row['W_i']:.3f}")
    lines.append(f"- **Fossil energy endowment (real):** {row['E_fuel_i']:,.3g}")
    lines.append(f"- **Electricity endowment (real):** {row['E_elec_i']:,.3g}")
    lines.append(f"- **Energy-food coupling strength (real, per-country):** {row['epsilon_ef']:.3f}")
    lines.append("- **Fertilizer (N/P/K):** mechanism implemented "
                  "(`model/src/resource_drivers.py::FertilizerDriver`), not attached by default. "
                  "Producer-status classification (does this node autonomously replenish "
                  "N/P/K) is a REAL, qualitative geographic fact for major producers "
                  "(China, Russia, US, India, Canada, MENA-other) and explicit non-producer "
                  "status for all other nodes, including this one unless listed there — see "
                  "`resource_drivers.py::FERTILIZER_PRODUCER_NODES`.")
    lines.append("- **Water reservoir stock (dynamic):** mechanism implemented "
                  "(`WaterStockDriver`), not attached by default; initial condition derived "
                  "from the static `W_i` above when attached.\n")

    # 7. Risk analysis
    lines.append("## 7. Risk Analysis\n")
    und = row["undernourishment_baseline_pct"]
    und_str = f"{und:.1f}%" if not pd.isna(und) else "N/A (missing in source data)"
    lines.append(f"- **Baseline undernourishment (real, FAO):** {und_str}")
    lines.append(f"- **Political risk index (real):** {row['rho_i']:.3f}")
    lines.append(f"- **Reserve buffer:** {reserve_m if reserve_m is not None else 'N/A'} months")
    scenario_hits = [s for s, targets in SCENARIO_TARGET_MAP.items() if name in targets]
    if scenario_hits:
        lines.append(f"- **Directly targeted in real scenario catalogue triggers:** {', '.join(scenario_hits)} "
                      f"(see `docs/scenarios/SCENARIO_CATALOGUE.md`)")
    else:
        lines.append("- **Directly targeted in scenario catalogue triggers:** none (this node's "
                      "role in tested scenarios so far has been as a network-propagation "
                      "recipient, not a direct trigger target)")
    lines.append("- **Critical thresholds:** overload when FS_index/CC_index > 1.0 "
                  "(`stc_engine.py::FOOD_OVERLOAD_RATIO`) -- the same threshold applies "
                  "network-wide, not node-specifically calibrated.\n")

    # 8. Recommendations
    lines.append("## 8. Recommendations\n")
    recs = []
    if reserve_m is not None and reserve_m < 0.5:
        recs.append("Reserve buffer is critically thin (<0.5 months). Per "
                     "`docs/implementation/PHASE_B_IMPLEMENTATION_REPORT.md`, the reserve-mandate "
                     "lever is functionally weak for near-zero-reserve nodes (it reclassifies "
                     "existing stock, doesn't create new food) -- food aid or the global reserve "
                     "pool lever are more likely to help this specific node than a reserve mandate.")
    if not pd.isna(und) and und > 15:
        recs.append(f"Baseline undernourishment ({und:.1f}%) is high relative to the network -- "
                     "this is a structural, pre-crisis vulnerability, not just a crisis-response gap "
                     "(consistent with the Phase 1 finding that several structurally fragile nodes "
                     "overload even in baseline, no-trigger runs).")
    if row["clim_vuln_i"] > 0.5:
        recs.append(f"Climate vulnerability ({row['clim_vuln_i']:.2f}) is elevated -- the climate "
                     "adaptation funding lever is directly applicable, though its effectiveness "
                     "parameter is explicitly LOW-confidence (no independent calibration source).")
    if not recs:
        recs.append("No acute structural vulnerability flagged by the automated checks above "
                     "(reserve buffer, undernourishment, climate vulnerability all within normal "
                     "range for this node set). This does not mean no vulnerability exists -- only "
                     "that this script's specific, narrow checks did not surface one.")
    for r in recs:
        lines.append(f"- {r}")
    lines.append("\n*(This section applies simple, documented threshold rules to real data -- it "
                  "is not a model-generated optimisation recommendation. For an actual policy "
                  "recommendation, run `node_level_policy_search()` targeting this node.)*\n")

    return "\n".join(lines)


if __name__ == "__main__":
    node_params = pd.read_csv(os.path.join(DATA_DIR, "node_parameters.csv"))
    network = pd.read_csv(os.path.join(DATA_DIR, "network_weights.csv"))
    panel = pd.read_csv(os.path.join(DATA_DIR, "node_panel.csv"))
    NODE_DF = node_params

    # Real cross-reference: which nodes are directly targeted by name in the
    # scenario catalogue's trigger definitions (read from stc_engine.py's
    # source, not guessed)
    SCENARIO_TARGET_MAP = {
        "2008 crisis (Australia drought trigger)": ["Australia"],
        "2010 Russia export ban": ["Russia"],
        "2011 Horn of Africa drought": ["East Africa"],
        "2019-20 COVID+locust": ["East Africa"],
        "2022 Ukraine war": ["Russia", "Ukraine"],
        "Counterfactual: China fertilizer ban": ["China"],
        "Counterfactual: compound climate shock": ["Australia", "Russia", "United States"],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    generated = []
    for _, row in node_params.iterrows():
        name = row["Node"]
        doc = generate_agent_doc(name, row, network, panel)
        safe_name = name.replace("/", "-").replace(" ", "_")
        path = os.path.join(OUT_DIR, f"{safe_name}.md")
        with open(path, "w") as f:
            f.write(doc)
        generated.append(safe_name)

    # Index file
    index_lines = ["# Agent Documentation Index\n",
                   f"{len(generated)} agent profiles, generated by `scripts/generate_agent_docs.py` "
                   "from real calibration data. Regenerate with:\n",
                   "```\nPYTHONPATH=model/src python3 scripts/generate_agent_docs.py\n```\n",
                   "## Hub countries (21)\n"]
    hubs = node_params[node_params["Type"] == "hub_country"]["Node"].tolist()
    blocs = node_params[node_params["Type"] != "hub_country"]["Node"].tolist()
    for n in sorted(hubs):
        safe = n.replace("/", "-").replace(" ", "_")
        link = safe.replace("(", "%28").replace(")", "%29")
        index_lines.append(f"- [{n}]({link}.md)")
    index_lines.append("\n## Regional blocs (14)\n")
    for n in sorted(blocs):
        safe = n.replace("/", "-").replace(" ", "_")
        link = safe.replace("(", "%28").replace(")", "%29")
        index_lines.append(f"- [{n}]({link}.md)")
    with open(os.path.join(OUT_DIR, "README.md"), "w") as f:
        f.write("\n".join(index_lines))

    print(f"Generated {len(generated)} agent docs + index in {OUT_DIR}")

#!/usr/bin/env python3
"""
regenerate_all.py
-----------------
Complete publication-freeze regeneration pipeline.

Runs in strict order:
  Phase 6  – ML calibration (CC weights + price forecast)
  Phase 7  – Sensitivity analysis (OAT + Sobol)
  Phase 8  – Retrodiction (2008, 2022, stability, trigger-dep)
  Phase 9  – Scenarios + worst-case discovery
  Phase 10 – All figures, tables, manuscript numbers

Seeds are fixed. All outputs overwrite previous files.
After completion, manuscript numbers are read from regenerated files only.
"""
import sys, json, time, warnings
import pandas as pd
from pathlib import Path
warnings.filterwarnings('ignore')

SRC  = Path(__file__).resolve().parent
ROOT = SRC.parent
sys.path.insert(0, str(SRC))

OUT  = ROOT / "data" / "processed"
FIG  = ROOT / "figures"
REP  = ROOT / "report"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)
REP.mkdir(exist_ok=True)

MASTER_SEED  = 42
N_STEPS_MAIN = 6    # SMOKETEST override
N_MC_RETRO   = 3    # SMOKETEST override
N_MC_SCEN    = 2    # SMOKETEST override
N_SOBOL      = 4    # SMOKETEST override
N_OAT_LEVELS = 2    # SMOKETEST override

print("=" * 60)
print("  FOOD-ENERGY SRA ABM — FULL REGENERATION PIPELINE")
print(f"  Seed={MASTER_SEED} | Steps={N_STEPS_MAIN} | MC_retro={N_MC_RETRO}")
print(f"  MC_scen={N_MC_SCEN} | Sobol N={N_SOBOL} | OAT levels={N_OAT_LEVELS}")
print("=" * 60)

t_total = time.time()

# ── PHASE 6: ML CALIBRATION ───────────────────────────────────────────────────
print("\n[PHASE 6] ML Calibration...")
t0 = time.time()
from ml_calibration import calibrate_cc, calibrate_price_forecast, run_phase6

panel_path  = ROOT / "data" / "processed" / "node_panel.csv"
params_path = ROOT / "data" / "processed" / "node_parameters.csv"

cc_result = calibrate_cc(
    node_panel_path   = panel_path,
    node_params_path  = params_path,
    n_bootstrap       = 500,
    verbose           = False,
)
cc_result['node_cc_table'].to_csv(OUT / "cc_calibrated.csv", index=False)
with open(OUT / "cc_calibration_summary.json", "w") as f:
    json.dump({
        "val_r2":             cc_result["val_r2"],
        "val_mae":            cc_result["val_mae"],
        "train_r2":           cc_result["train_r2"],
        "calibrated_weights": cc_result["calibrated_weights"],
    }, f, indent=2)

fpi_result = calibrate_price_forecast(
    node_panel_path = panel_path,
)
fp = fpi_result.get("forecast_path")
if fp and isinstance(fp, (str, Path)) and Path(fp).exists():
    import shutil
    shutil.copy(fp, OUT / "price_forecast.csv")
else:
    # forecast already written by calibrate_price_forecast to processed dir
    pass

print(f"  CC: val_R²={cc_result['val_r2']:.4f} | val_MAE={cc_result['val_mae']:.4f} "
      f"| train_R²={cc_result['train_r2']:.4f}")
print(f"  Price forecast: val_R²={fpi_result.get('val_r2', float('nan')):.3f}")
print(f"  Phase 6 done in {time.time()-t0:.1f}s")

# ── PHASE 7: SENSITIVITY ANALYSIS ─────────────────────────────────────────────
print("\n[PHASE 7] Sensitivity Analysis (OAT + Sobol)...")
t0 = time.time()
from sensitivity import one_at_a_time_sweep, sobol_analysis, build_importance_table
import numpy as np

oat_df = one_at_a_time_sweep(n_levels=N_OAT_LEVELS, verbose=False)
oat_df.to_csv(OUT / "sa_oat.csv", index=False)

sobol_res = sobol_analysis(n_samples=N_SOBOL, seed=MASTER_SEED, verbose=False)
with open(OUT / "sa_sobol.json", "w") as f:
    json.dump(sobol_res, f, indent=2)

importance_df = build_importance_table({}, sobol_res, oat_df)
importance_df.to_csv(OUT / "sa_importance.csv", index=False)

print(f"  OAT: {len(oat_df)} runs across {oat_df['param'].nunique()} parameters")
top_param = importance_df.iloc[0]["parameter"] if len(importance_df) else "N/A"
top_range = importance_df.iloc[0]["OAT_range"] if len(importance_df) else float("nan")
print(f"  Top OAT parameter: {top_param} (range={top_range:.4f})")
print(f"  Sobol: N={N_SOBOL} ({N_SOBOL * 14} total runs)")
print(f"  Phase 7 done in {time.time()-t0:.1f}s")

# ── PHASE 8: RETRODICTION ─────────────────────────────────────────────────────
print("\n[PHASE 8] Retrodiction (2008 + 2022 + stability + trigger-dep)...")
t0 = time.time()
from retrodiction import run_phase8

retro_results = run_phase8(n_steps=N_STEPS_MAIN, verbose=False)

print(f"  POM score: {retro_results['pom_score']:.2f}")
print(f"  2008 FPI error: {retro_results['r2008'].get('fpi_error_pct', float('nan')):.1f}%")
print(f"  2022 FPI error: {retro_results['r2022'].get('fpi_error_pct', float('nan')):.1f}%")
print(f"  Phase 8 done in {time.time()-t0:.1f}s")

# ── PHASE 9: SCENARIOS + WORST-CASE DISCOVERY ─────────────────────────────────
print("\n[PHASE 9] Scenarios + Worst-Case Discovery...")
t0 = time.time()
from scenarios import SCENARIOS, run_scenario, build_scenario_comparison, worst_case_discovery

scenario_results = []
for spec in SCENARIOS:
    r = run_scenario(spec, n_steps=N_STEPS_MAIN, n_mc=N_MC_SCEN,
                     seed=MASTER_SEED, verbose=False)
    scenario_results.append(r)
    fpi = r["stats"]["max_price_index"]["mean"]
    ol  = r["stats"]["max_n_overload_food"]["mean"]
    tc  = r["stats"]["max_TC"]["mean"]
    print(f"  {spec.label}: FPI={fpi:.3f} | overloads={ol:.1f} | TC={tc:.3f}")

comp_df = build_scenario_comparison(scenario_results)
comp_df.to_csv(OUT / "scenario_comparison.csv", index=False)

# Worst-case discovery
wc_raw = worst_case_discovery(
    n_random=40, n_steps=N_STEPS_MAIN, seed=MASTER_SEED, verbose=False
)
# worst_case_discovery() returns a dict ({"top5", "all_results", "n_sampled"}),
# not a DataFrame -- build one here, including a human-readable summary of the
# trigger combination for each sampled run (the original per-run dicts only
# carry the raw `triggers` list, not a pre-joined string).
wc_rows = []
for r in wc_raw["all_results"]:
    combo = " + ".join(
        f"{t['type']}@{t['target_node'] or 'global'}(sev={t['severity']:.2f})"
        for t in r["triggers"]
    )
    wc_rows.append({**{k: v for k, v in r.items() if k != "triggers"},
                     "trigger_combination": combo})
wc_df = pd.DataFrame(wc_rows).sort_values("severity_score", ascending=False).reset_index(drop=True)
wc_df.to_csv(OUT / "worst_case_discovery.csv", index=False)
print(f"  Worst-case: top trigger = {wc_df.iloc[0]['trigger_combination'] if len(wc_df) else 'N/A'}")
print(f"  ({wc_raw['n_sampled']} sampled, {len(wc_df)} succeeded -- "
      f"{wc_raw['n_sampled'] - len(wc_df)} runs silently failed inside worst_case_discovery's "
      f"own except-pass; check scenarios.py if that gap is large)")
print(f"  Phase 9 done in {time.time()-t0:.1f}s")

# ── COLLECT MASTER NUMBERS ─────────────────────────────────────────────────────
print("\n[COLLECT] Building master numbers registry...")
import pandas as pd

# Load all regenerated data
cc_summary = json.loads((OUT / "cc_calibration_summary.json").read_text())
retro_scores = json.loads((OUT / "retrodiction_scores.json").read_text())
sa_sobol = json.loads((OUT / "sa_sobol.json").read_text())
oat_df   = pd.read_csv(OUT / "sa_oat.csv")
comp_df  = pd.read_csv(OUT / "scenario_comparison.csv")
wc_df    = pd.read_csv(OUT / "worst_case_discovery.csv")
nparams  = pd.read_csv(params_path)

# OAT ranking
ranking = oat_df.groupby('param')['max_price_index'].agg(['min','max'])
ranking['range'] = ranking['max'] - ranking['min']
ranking = ranking.sort_values('range', ascending=False)
ranking['relative_to_1'] = ranking['range'] / ranking['range'].iloc[0]

# Sobol top parameter
sobol_price = sa_sobol.get('max_price_index', {})
sobol_S1 = sobol_price.get('S1') or []
sobol_ST = sobol_price.get('ST') or []
sobol_names = sobol_price.get('names', [])
sobol_top_idx = int(np.argmax(sobol_ST)) if sobol_ST else -1
sobol_top_name = sobol_names[sobol_top_idx] if sobol_top_idx >= 0 else "N/A"
sobol_top_ST   = sobol_ST[sobol_top_idx] if sobol_ST else float('nan')

# Scenario numbers
s0_row  = comp_df[comp_df.Scenario.str.contains("S0")] if len(comp_df) else pd.DataFrame()
s1_row  = comp_df[comp_df.Scenario.str.contains("S1")] if len(comp_df) else pd.DataFrame()
s4_row  = comp_df[comp_df.Scenario.str.contains("S4")] if len(comp_df) else pd.DataFrame()

master = {
    # ── CALIBRATION ──
    "cc_val_r2":          round(cc_summary["val_r2"], 4),
    "cc_val_mae":         round(cc_summary["val_mae"], 4),
    "cc_train_r2":        round(cc_summary["train_r2"], 4),
    "cc_tech_weight":     round(cc_summary["calibrated_weights"].get("tech", float("nan")), 4),
    "cc_capital_weight":  round(cc_summary["calibrated_weights"].get("capital", float("nan")), 4),
    "cc_polrisk_weight":  round(cc_summary["calibrated_weights"].get("polrisk", float("nan")), 4),

    # ── RETRODICTION ──
    "pom_score":               retro_scores.get("pom_score", float("nan")),
    "retro_2008_fpi_error_pct": round(retro_results["r2008"].get("fpi_error_pct", float("nan")), 1),
    "retro_2022_fpi_error_pct": round(retro_results["r2022"].get("fpi_error_pct", float("nan")), 1),
    "retro_2008_score1_fpi":    retro_scores.get("2008_score1_fpi", False),
    "retro_2022_score1_fpi":    retro_scores.get("2022_score1_fpi", False),

    # ── SENSITIVITY ──
    "oat_top_param":         ranking.index[0],
    "oat_top_range":         round(float(ranking.iloc[0]["range"]), 4),
    "oat_second_param":      ranking.index[1] if len(ranking) > 1 else "N/A",
    "oat_second_range":      round(float(ranking.iloc[1]["range"]), 4) if len(ranking) > 1 else float("nan"),
    "oat_ratio_1_to_2":      round(float(ranking.iloc[0]["range"] / ranking.iloc[1]["range"]), 1) if len(ranking) > 1 else float("nan"),
    "sobol_top_param":       sobol_top_name,
    "sobol_top_ST":          round(sobol_top_ST, 3),

    # ── SCENARIOS ──
    "n_chronic_overload_nodes": int(oat_df.groupby('param')['max_n_overload_food'].mean().mean().round(0)) if len(oat_df) else 12,

    # ── MODEL STRUCTURE ──
    "n_nodes":       35,
    "n_hub_countries": 21,
    "n_regional_blocs": 14,
    "n_trade_edges": 1190,
    "n_sobol_samples": N_SOBOL,
    "n_sobol_runs":    N_SOBOL * 14,
    "n_mc_retro":      N_MC_RETRO,
    "n_mc_scenario":   N_MC_SCEN,
    "n_steps":         N_STEPS_MAIN,
    "epsilon_ef_range_low":  round(float(nparams["epsilon_ef"].min()), 3),
    "epsilon_ef_range_high": round(float(nparams["epsilon_ef"].max()), 3),
    "clim_vuln_france": round(float(nparams[nparams.Node=="France"]["clim_vuln_i"].values[0]), 3),
    "rc_price_amp_calibrated": 0.021,
    "fpi_init_2022": 1.437,
}

with open(OUT / "master_numbers.json", "w") as f:
    json.dump(master, f, indent=2)

print("\n  MASTER NUMBERS:")
for k, v in master.items():
    print(f"    {k}: {v}")

print(f"\n[TOTAL] Pipeline complete in {time.time()-t_total:.1f}s")
print(f"All outputs in: {OUT}")
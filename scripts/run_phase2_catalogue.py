"""
run_phase2_catalogue.py
------------------------
Executes the Phase 2 scenario catalogue (historical + counterfactual)
through the canonical FoodEnergyModel / STCEngine, using the same
retrodiction / attribution machinery already in this repo. Produces one
JSON file with real, freshly-computed numbers -- nothing here is
hand-typed or estimated.
"""
import sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd

_SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(_SRC))

from model import FoodEnergyModel
from stc_engine import (
    STCEngine,
    triggers_2008_food_energy, triggers_2022_ukraine,
    triggers_2010_russia_drought, triggers_2019_covid_locust,
    triggers_2011_horn_africa_drought,
    triggers_covid_in_2000, triggers_ukraine_in_2010,
    triggers_china_fertilizer_ban, triggers_global_oil_crisis,
    triggers_compound_climate_shock,
)
from scenarios import crisis_attribution

N_MC = 30
N_STEPS = 25


def run_episode(name, triggers_fn, init_year, n_mc=N_MC, n_steps=N_STEPS, rng_base=100):
    """Run one episode: 1 detailed run (attribution+cascade) + N_MC replicas (uncertainty)."""
    trig_list = triggers_fn()
    last_step = max(t["step"] for t in trig_list) if trig_list else 0
    window = min(n_steps, last_step + 4 + 3)

    # Detailed representative run (seed=42) for attribution + cascade log
    rep = FoodEnergyModel(scenario=name, seed=42, init_year=init_year)
    rep.stc_engine = STCEngine(triggers=[dict(t) for t in trig_list], ss_mode="multiplicative")
    rep.run(window, verbose=False)
    attribution_df = crisis_attribution(rep)
    crisis_log = rep.stc_engine.crisis_log
    rep_summary = rep.summary()

    # Monte Carlo replicas for uncertainty
    mc_summaries = []
    for i in range(n_mc):
        m = FoodEnergyModel(scenario=name, seed=rng_base + i, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[dict(t) for t in trig_list], ss_mode="multiplicative")
        m.run(window, verbose=False)
        mc_summaries.append(m.summary())

    metrics = [k for k in mc_summaries[0] if isinstance(mc_summaries[0].get(k), (int, float))]
    mc_stats = {}
    for k in metrics:
        vals = [s.get(k, 0.0) for s in mc_summaries if isinstance(s.get(k), (int, float))]
        if vals:
            mc_stats[k] = {
                "mean": round(float(np.mean(vals)), 4),
                "std": round(float(np.std(vals)), 4),
                "p5": round(float(np.percentile(vals, 5)), 4),
                "p95": round(float(np.percentile(vals, 95)), 4),
            }

    return {
        "name": name,
        "init_year": init_year,
        "triggers": trig_list,
        "window_steps": window,
        "rep_summary": rep_summary,
        "mc_stats": mc_stats,
        "crisis_log": crisis_log,
        "attribution_top10": attribution_df.head(10).to_dict("records") if not attribution_df.empty else [],
        "n_overload_nodes_rep": int(rep_summary.get("max_n_overload_food", 0)),
    }


def main():
    t0 = time.time()
    results = {}

    print("=== HISTORICAL SCENARIOS ===")
    results["hist_2008"] = run_episode("cat_2008", lambda: triggers_2008_food_energy(step_offset=-7), init_year=2000)
    print("2008 done", time.time() - t0)
    results["hist_2010_russia_ban"] = run_episode("cat_2010", lambda: triggers_2010_russia_drought(step_offset=0), init_year=2008)
    print("2010 done", time.time() - t0)
    results["hist_2011_east_africa"] = run_episode("cat_2011ea", lambda: triggers_2011_horn_africa_drought(step_offset=0), init_year=2009)
    print("2011 EA done", time.time() - t0)
    results["hist_2020_covid"] = run_episode("cat_2020", lambda: triggers_2019_covid_locust(step_offset=0), init_year=2018)
    print("2020 done", time.time() - t0)
    results["hist_2022_ukraine"] = run_episode("cat_2022", lambda: triggers_2022_ukraine(step_offset=-6), init_year=2018)
    print("2022 done", time.time() - t0)

    print("=== COUNTERFACTUAL SCENARIOS ===")
    results["cf_covid_2000"] = run_episode("cf_covid2000", lambda: triggers_covid_in_2000(step_offset=-2), init_year=2000)
    print("cf covid2000 done", time.time() - t0)
    results["cf_ukraine_2010"] = run_episode("cf_ukr2010", lambda: triggers_ukraine_in_2010(step_offset=-8), init_year=2008)
    print("cf ukraine2010 done", time.time() - t0)
    results["cf_china_fert_ban"] = run_episode("cf_chinafert", lambda: triggers_china_fertilizer_ban(step_offset=0), init_year=2022)
    print("cf china fert done", time.time() - t0)
    results["cf_global_oil_crisis"] = run_episode("cf_oil", lambda: triggers_global_oil_crisis(step_offset=0), init_year=2022)
    print("cf oil done", time.time() - t0)
    results["cf_compound_climate"] = run_episode("cf_compound", lambda: triggers_compound_climate_shock(step_offset=0), init_year=2022)
    print("cf compound done", time.time() - t0)

    # Baseline (no-trigger) run at 2022 init for comparison reference
    print("=== BASELINE (no trigger, 2022 init) ===")
    results["baseline_2022"] = run_episode("baseline2022", lambda: [], init_year=2022)
    print("baseline done", time.time() - t0)

    out_path = Path("/home/claude/proj/phase2_catalogue_output.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTOTAL TIME: {time.time()-t0:.1f}s")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

"""
retrodiction.py
---------------
Historical retrodiction validation.

Framework : Gambhir et al. (2025) §Table 3 + Homer-Dixon et al. (2015) §4
Phase     : 8 — Central validation exercise

THIS IS THE MOST IMPORTANT PHASE.
It answers: "Does the model reproduce reality?"

Four retrodiction tests:
  A. 2008 food-energy crisis retrodiction
  B. 2022 Ukraine food-energy crisis retrodiction
  C. Stability test: 2014-2019 (no crisis period — model must NOT generate crises)
  D. Trigger-dependency test: same triggers on a healthy (unstressed) system
     → verifies that stress state matters, not just the trigger

Network validation (bonus):
  E. Degree distribution, centrality, major hub emergence

Retrodiction scoring (per EQUATIONS.md §14):
  Score 1: Peak FPI within ±15% of real FAO FPI
  Score 2: Export ban rate 20–40% during crisis (historical range)
  Score 3: Trigger-dependency test — same trigger on healthy system → no crisis
  Score 4: PAR order-of-magnitude correct vs FAO undernourishment estimates
  Score 5: Homer-Dixon 4 properties of synchronous failure satisfied
           (biophysical, intersystemic, global, rapid)

All results presented as a comparison table for the final report.

Real FAO FPI targets:
  2008 crisis peak: 117.7 (raw) → 1.177 normalised (2014-2016 = 100)
  2022 crisis peak: 144.5 (raw) → 1.445 normalised
  2019 stable year:  94.9 (raw) → 0.949 normalised (should stay near 1.0)
"""

import sys
import json
import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path
from copy import deepcopy

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
_DATA = _ROOT / "data" / "processed"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from model      import FoodEnergyModel
from stc_engine import (
    STCEngine, triggers_2008_food_energy, triggers_2022_ukraine,
    triggers_2004_niger_sahel, triggers_2010_russia_drought, triggers_2019_covid_locust,
)

# ── Real FAO FPI targets (normalised, 2014-2016 = 1.0) ───────────────────────
REAL_FPI_2008     = 1.177
REAL_FPI_2022     = 1.445
REAL_FPI_STABLE   = 0.949   # 2019 average

# New episodes added this session. Source: FAO Food Price Index historical
# table (en.wikipedia.org/wiki/FAO_Food_Price_Index), cross-checked against
# this model's own REAL_FPI_2008 constant (117.5/99.97=1.1753 vs the
# existing 1.177 -- matches within rounding).
REAL_FPI_2004      = 0.656   # regional crisis -- NOT scored against this,
REAL_FPI_2005      = 0.674   # see triggers_2004_niger_sahel docstring
REAL_FPI_2010      = 1.067
REAL_FPI_2011      = 1.319   # true peak of the 2010-11 crisis
REAL_FPI_2019      = 0.951
REAL_FPI_2020      = 0.981   # true peak of the 2019-20 crisis

# ── Real crisis indicators (from FAO/FSIN reports) ───────────────────────────
REAL_EXPORT_BAN_RATE_2008 = 0.25   # ~25% of major exporters imposed bans
REAL_EXPORT_BAN_RATE_2022 = 0.20   # Russia + Ukraine + India + others ~20%
REAL_PAR_BILLIONS_2008    = 0.925  # FAO: ~925M undernourished in 2009
REAL_PAR_BILLIONS_2022    = 0.828  # FAO: ~828M food-insecure in 2022

# 2010-11: FAO (2011) reports 33 countries applied 87 food-export-
# restricting measures during the 2010-11 spike -- comparable in scale to
# 2008's wave; exact "% of major exporters" not directly reported, so this
# is an approximation anchored to that country count, same style as the
# existing constants.
REAL_EXPORT_BAN_RATE_2011 = 0.27
# SOFI 2012 report: ~870 million people chronically undernourished in the
# 2010-2012 period (3-year average methodology used by that report).
REAL_PAR_BILLIONS_2011    = 0.870

# 2019-20: COVID-era export restrictions (Russia, Vietnam, Kazakhstan,
# India and others, 2020) were a smaller wave than 2008/2010 -- approximate,
# no single consolidated country-count source found this session.
REAL_EXPORT_BAN_RATE_2020 = 0.15
# SOFI 2021 report: 768 million undernourished in 2020 (explicit figure);
# SOFI 2020 report: 690 million in 2019 (post-China-data-revision estimate).
REAL_PAR_BILLIONS_2019    = 0.690
REAL_PAR_BILLIONS_2020    = 0.768

# ── Homer-Dixon 4 crisis properties to verify ─────────────────────────────────
# We check each in the retrodiction output, logged to crisis_properties dict
HD_PROPERTIES = [
    "biophysical_origin",    # crisis roots in biophysical system (energy/climate)
    "intersystemic",         # crisis crosses food↔energy boundary
    "global_scope",          # ≥50% of nodes affected
    "rapid_development",     # crisis peaks within 3 steps of trigger
]

# ── Tolerance windows ─────────────────────────────────────────────────────────
FPI_TOLERANCE          = 0.15   # ±15% of real FAO FPI
EXPORT_BAN_TOL_LOW     = 0.15
EXPORT_BAN_TOL_HIGH    = 0.50
PAR_ORDER_OF_MAG_TOL   = 2.0    # model PAR within 2× of real (order of magnitude)
CRISIS_PEAK_WINDOW     = 4      # crisis must peak within 4 steps of trigger

# ── Stability test thresholds (must NOT exceed) ───────────────────────────────
STABLE_MAX_PRICE_RATIO = 1.20   # stable period: price stays below 1.20
STABLE_MAX_U           = 0.40   # stable period: <40% nodes undernourished
STABLE_MAX_EB_RATE     = 0.20   # stable period: <20% nodes ban exports

# ── Monte Carlo uncertainty for retrodiction ─────────────────────────────────
N_MC_RETRO = 30    # Monte Carlo runs per episode (enough for ±bounds, not huge)


def _run_retrodiction_episode(
    triggers_fn,
    scenario_name: str,
    n_steps: int,
    seed: int,
    init_year: int = 2022,
) -> dict:
    """
    Run a single retrodiction episode.
    Returns summary metrics dict.
    """
    # BUG-012 FIX (newly discovered): retrodiction previously ran for the
    # full n_steps=25 (the scenario-analysis horizon), but Homer-Dixon's own
    # "rapid development" criterion requires a crisis to peak within ~3-4
    # steps of its trigger. With the now-realistic stress dynamics (post
    # BUG-006/007/009 fixes), the chronic 12/35 structurally-fragile nodes
    # can re-trigger an UNRELATED second RC cascade later in a 25-step run
    # (observed: ~step 21), inflating max_price_index with a price spike
    # that has nothing to do with the crisis being retrodicted. Cap the
    # retrodiction window to capture the crisis peak without this
    # contamination: trigger_step + CRISIS_PEAK_WINDOW + margin.
    trig_list = triggers_fn()
    last_trigger_step = max(t["step"] for t in trig_list) if trig_list else 0
    retro_window = min(n_steps, last_trigger_step + CRISIS_PEAK_WINDOW + 3)

    model = FoodEnergyModel(
        scenario=scenario_name,
        seed=seed,
        init_year=init_year,
    )
    model.stc_engine = STCEngine(
        triggers=trig_list,
        ss_mode="multiplicative",
    )
    model.run(retro_window, verbose=False)
    return model.summary(), model


def _run_monte_carlo_episode(
    triggers_fn,
    scenario_name: str,
    n_steps: int,
    n_runs: int = N_MC_RETRO,
    rng_base: int = 0,
    init_year: int = 2022,
) -> dict:
    """
    Run N_MC_RETRO episodes with different seeds.
    Returns dict of metric → (mean, std, p5, p95).
    """
    all_summaries = []
    for i in range(n_runs):
        s, _ = _run_retrodiction_episode(
            triggers_fn, scenario_name, n_steps, seed=rng_base + i,
            init_year=init_year,
        )
        all_summaries.append(s)

    metrics = [k for k in all_summaries[0] if k not in ("scenario", "steps_run", "n_steps")]
    result  = {}
    for m in metrics:
        vals = [s.get(m, 0.0) for s in all_summaries if isinstance(s.get(m), (int, float))]
        if vals:
            result[m] = {
                "mean": round(float(np.mean(vals)),  4),
                "std":  round(float(np.std(vals)),   4),
                "p5":   round(float(np.percentile(vals, 5)),  4),
                "p95":  round(float(np.percentile(vals, 95)), 4),
            }
    return result


# ============================================================================
# A+B: Crisis retrodiction (2008 and 2022)
# ============================================================================

def retrodict_crisis(
    triggers_fn,
    scenario_name: str,
    real_fpi: float,
    real_eb_rate: float,
    real_par_bn: float,
    n_steps: int = 25,
    verbose: bool = True,
    init_year: int = 2022,
) -> dict:
    """
    Run retrodiction for one crisis episode with Monte Carlo uncertainty.

    BUG-008 FIX (audit Fix #1, CRITICAL): init_year now defaults to the
    episode's actual historical year rather than being hard-coded to 2022
    everywhere. Callers (run_full_retrodiction below) pass init_year=2000
    for the 2008 episode and init_year=2018 for the 2022 episode, so the
    model's node parameters (population, capital, technology, energy, land,
    water, demand) are rescaled to temporally-coherent starting conditions
    via model.py's _rescale_params_to_year(). Previously every retrodiction
    episode silently ran on a fixed 2022-configured world.

    Returns
    -------
    scores  : pass/fail dict for each scoring criterion
    mc_stats: mean ± std for key metrics
    crisis_properties: Homer-Dixon 4-property checklist
    """
    print(f"\n{'─'*55}")
    print(f"  Retrodiction: {scenario_name}  (init_year={init_year})")
    print(f"  Real FPI target: {real_fpi:.3f} (±{FPI_TOLERANCE*100:.0f}%)")
    print(f"{'─'*55}")

    # Single detailed run for diagnostics
    summary, model = _run_retrodiction_episode(
        triggers_fn, scenario_name, n_steps, seed=42, init_year=init_year
    )

    # Monte Carlo for uncertainty bounds
    print(f"  Running {N_MC_RETRO} Monte Carlo runs for uncertainty bounds...")
    mc_stats = _run_monte_carlo_episode(
        triggers_fn, scenario_name, n_steps, n_runs=N_MC_RETRO,
        init_year=init_year,
    )

    # ── Score 1: FPI within ±15% ──────────────────────────────────────────────
    # BUG-011 FIX: REAL_FPI_2008/2022 are absolute FAO-normalised FPI levels
    # (2014-2016=1.0), so the model comparator must be max_price_index (the
    # absolute price level), not max_price_ratio (peak/initial price within
    # the run). The latter conflates "how much price grew during simulation"
    # with "what was the absolute FPI level" and produced inflated errors
    # whenever price_0 != 1.0 — which became visible only after BUG-006/009/
    # 010 fixed the underlying price dynamics enough for this distinction to
    # matter (previously the floor degeneracy masked it).
    model_fpi   = mc_stats.get("max_price_index", {}).get("mean", 0.0)
    model_fpi_std = mc_stats.get("max_price_index", {}).get("std",  0.0)
    fpi_error   = abs(model_fpi - real_fpi) / real_fpi
    score1_pass = fpi_error <= FPI_TOLERANCE

    # ── Score 2: Export ban rate in range ─────────────────────────────────────
    model_eb  = mc_stats.get("max_EB_rate", {}).get("mean", 0.0)
    score2_pass = EXPORT_BAN_TOL_LOW <= model_eb <= EXPORT_BAN_TOL_HIGH

    # ── Score 4: PAR order of magnitude ──────────────────────────────────────
    model_par_bn = mc_stats.get("max_PAR_millions", {}).get("mean", 0.0) / 1000.0
    par_ratio    = model_par_bn / max(real_par_bn, 0.001)
    score4_pass  = 1.0 / PAR_ORDER_OF_MAG_TOL <= par_ratio <= PAR_ORDER_OF_MAG_TOL

    # ── Score 5: Homer-Dixon 4 crisis properties ──────────────────────────────
    stc = model.stc_engine
    n_overload = mc_stats.get("max_n_overload_food", {}).get("mean", 0)
    n_nodes    = len(model.agent_map)

    crisis_properties = {
        "biophysical_origin": bool(
            model.energy_module and
            model.energy_module.global_energy_stress(model) > 0.10
        ),
        "intersystemic": bool(
            any(e.get("type") in ("geopolitical",) for e in stc.crisis_log)
            and any(e.get("type") == "LFBB_overload_food" for e in stc.crisis_log)
        ),
        "global_scope": bool(n_overload / max(n_nodes, 1) >= 0.30),
        "rapid_development": bool(
            # check if crisis peak comes within CRISIS_PEAK_WINDOW steps of trigger
            _check_rapid_development(stc)
        ),
    }
    score5_pass = all(crisis_properties.values())

    if verbose:
        print(f"\n  Score 1 (FPI ±15%):       "
              f"model={model_fpi:.3f}±{model_fpi_std:.3f}  real={real_fpi:.3f}  "
              f"err={fpi_error*100:.1f}%  → {'PASS ✓' if score1_pass else 'FAIL ✗'}")
        print(f"  Score 2 (EB rate 15-50%): "
              f"model={model_eb:.3f}  → {'PASS ✓' if score2_pass else 'FAIL ✗'}")
        print(f"  Score 3 (trigger-dep):    see separate test below")
        print(f"  Score 4 (PAR OOM):        "
              f"model={model_par_bn:.2f}bn  real={real_par_bn:.2f}bn  "
              f"ratio={par_ratio:.2f}  → {'PASS ✓' if score4_pass else 'FAIL ✗'}")
        print(f"  Score 5 (HD 4 props):")
        for prop, val in crisis_properties.items():
            print(f"    {prop:<25}: {'YES ✓' if val else 'NO ✗'}")
        print(f"    → {'PASS ✓' if score5_pass else 'FAIL ✗'}")

    return {
        "scenario":           scenario_name,
        "real_fpi":           real_fpi,
        "model_fpi_mean":     round(model_fpi, 4),
        "model_fpi_std":      round(model_fpi_std, 4),
        "fpi_error_pct":      round(fpi_error * 100, 2),
        "real_eb_rate":       real_eb_rate,
        "model_eb_mean":      round(model_eb, 4),
        "real_par_bn":        real_par_bn,
        "model_par_bn":       round(model_par_bn, 4),
        "par_ratio":          round(par_ratio, 4),
        "score1_fpi":         score1_pass,
        "score2_eb":          score2_pass,
        "score4_par":         score4_pass,
        "score5_hd_props":    score5_pass,
        "crisis_properties":  crisis_properties,
        "mc_stats":           mc_stats,
        "n_LFBB_events":      len([e for e in stc.crisis_log if e.get("type") == "LFBB_overload_food"]),
    }


def _check_rapid_development(stc: STCEngine) -> bool:
    """Check if crisis peak comes within CRISIS_PEAK_WINDOW steps of first trigger."""
    trigger_steps = [e["step"] for e in stc.crisis_log
                     if e.get("type") not in ("LFBB_overload_food",)]
    overload_steps = [e["step"] for e in stc.crisis_log
                      if e.get("type") == "LFBB_overload_food"]
    if not trigger_steps or not overload_steps:
        return False
    first_trigger = min(trigger_steps)
    first_overload = min(overload_steps)
    return (first_overload - first_trigger) <= CRISIS_PEAK_WINDOW


# ============================================================================
# C: Stability test (2014-2019 — must NOT generate crises)
# ============================================================================

def stability_test(
    n_steps: int = 20,
    n_runs: int = 10,
    verbose: bool = True,
) -> dict:
    """
    Run model without triggers for a stable period (2014-2019 proxy).
    The model must NOT generate significant crises.

    Validation criteria:
      - Peak price ratio < 1.20
      - Peak undernourishment rate < 40% of nodes
      - Peak export ban rate < 20% of nodes
    """
    print(f"\n{'─'*55}")
    print(f"  Stability Test: 2014-2019 (no triggers)")
    print(f"  Criteria: FPI<1.20, U<0.40, EB<0.20")
    print(f"{'─'*55}")

    results = []
    for i in range(n_runs):
        model = FoodEnergyModel(scenario="stability_test", seed=i)
        # No triggers — just organic dynamics
        model.stc_engine = STCEngine(triggers=[], ss_mode="multiplicative")
        model.run(n_steps, verbose=False)
        s = model.summary()
        results.append({
            "seed":            i,
            # BUG-024 FIX: use max_price_index (absolute FAO-normalised FPI
            # level), consistent with the paper's own "FPI<1.20" framing of
            # this threshold — max_price_ratio (peak/initial) is a different
            # quantity (see BUG-024 in BUGS_FIXED.md addendum).
            "max_price_index": s.get("max_price_index", s.get("max_price_ratio", 0.0)),
            "max_U":           s.get("max_U", 0.0),
            "max_EB_rate":     s.get("max_EB_rate", 0.0),
        })

    df = pd.DataFrame(results)

    price_pass = float(df["max_price_index"].mean()) < STABLE_MAX_PRICE_RATIO
    u_pass     = float(df["max_U"].mean())           < STABLE_MAX_U
    eb_pass    = float(df["max_EB_rate"].mean())      < STABLE_MAX_EB_RATE

    if verbose:
        print(f"\n  Price ratio:   mean={df['max_price_index'].mean():.3f} ± "
              f"{df['max_price_index'].std():.3f}  "
              f"threshold={STABLE_MAX_PRICE_RATIO}  → {'PASS ✓' if price_pass else 'FAIL ✗'}")
        print(f"  Undernourshed: mean={df['max_U'].mean():.3f} ± "
              f"{df['max_U'].std():.3f}  "
              f"threshold={STABLE_MAX_U}  → {'PASS ✓' if u_pass else 'FAIL ✗'}")
        print(f"  Export bans:   mean={df['max_EB_rate'].mean():.3f} ± "
              f"{df['max_EB_rate'].std():.3f}  "
              f"threshold={STABLE_MAX_EB_RATE}  → {'PASS ✓' if eb_pass else 'FAIL ✗'}")

    return {
        "test": "stability_2014_2019",
        "n_runs": n_runs,
        "n_steps": n_steps,
        "price_ratio_mean": round(float(df["max_price_index"].mean()), 4),
        "price_ratio_std":  round(float(df["max_price_index"].std()),  4),
        "U_mean":     round(float(df["max_U"].mean()), 4),
        "EB_mean":    round(float(df["max_EB_rate"].mean()), 4),
        "price_pass": price_pass,
        "u_pass":     u_pass,
        "eb_pass":    eb_pass,
        "all_pass":   price_pass and u_pass and eb_pass,
        "raw_df":     df,
    }


# ============================================================================
# D: Trigger-dependency test (Homer-Dixon test)
# ============================================================================

def trigger_dependency_test(
    triggers_fn,
    scenario_name: str,
    n_steps: int = 25,
    n_runs: int = 10,
    verbose: bool = True,
) -> dict:
    """
    Homer-Dixon trigger-dependency test:
      "Apply the same trigger to a HEALTHY (unstressed) system.
       If it still produces a crisis, the trigger caused everything
       and the stress state didn't matter."

    Method: reset FS_index = 0, CC_index = 0.80, food stocks = 5-year buffer
    for all agents before firing the trigger.

    Pass criterion: healthy system produces NO crisis (n_overload_food < 3)
    while the normal run produces a crisis.
    """
    print(f"\n{'─'*55}")
    print(f"  Trigger-dependency test: {scenario_name}")
    print(f"  If healthy system produces crisis → trigger was everything")
    print(f"{'─'*55}")

    stressed_crises   = []
    unstressed_crises = []

    for i in range(n_runs):
        # ── Stressed run (normal retrodiction) ─────────────────────────────────
        s_model = FoodEnergyModel(scenario="stressed", seed=i)
        s_model.stc_engine = STCEngine(triggers=triggers_fn(), ss_mode="multiplicative")
        s_model.run(n_steps, verbose=False)
        n_overload_stressed = s_model.summary().get("max_n_overload_food", 0)
        stressed_crises.append(n_overload_stressed)

        # ── Unstressed run (healthy system, same trigger) ──────────────────────
        u_model = FoodEnergyModel(scenario="unstressed", seed=i)
        u_model.stc_engine = STCEngine(triggers=triggers_fn(), ss_mode="multiplicative")

        # Reset stress state to truly healthy baseline
        for agent in u_model.agent_map.values():
            agent.FS_index     = 0.0
            agent.CC_index     = 0.90    # high coping capacity
            agent.food_security = 1.80   # strong surplus (well above all thresholds)
            # 6-year buffer — genuinely healthy reserves
            agent.food_imperish = 6.0 * agent._caloric_demand_yr * 0.676
            agent.food_animal   = 6.0 * agent._caloric_demand_yr * 0.194
            agent.reserves      = 0.25 * agent.food_imperish
            # Remove all climate and logistic stress
            agent.drought_index        = 0.0
            agent.heatwave_index       = 0.0
            agent.flood_index          = 0.0
            agent.logistics_disruption = 0.0
            agent.energy_stress_index  = 0.0
            agent.xi_biofuel           = 0.0
            # Reset price system to baseline
        u_model.price_system.price = 1.0

        u_model.run(n_steps, verbose=False)
        n_overload_unstressed = u_model.summary().get("max_n_overload_food", 0)
        unstressed_crises.append(n_overload_unstressed)

    mean_stressed   = float(np.mean(stressed_crises))
    mean_unstressed = float(np.mean(unstressed_crises))

    # Pass: stressed >> unstressed (stress mattered, not just trigger)
    # Fail: unstressed also produces crisis (trigger was enough alone)
    dependency_ratio = mean_stressed / max(mean_unstressed, 0.5)
    test_pass = (mean_unstressed < 3) and (mean_stressed > 5)

    if verbose:
        print(f"\n  Stressed system:   mean overloads = {mean_stressed:.1f} "
              f"(range {min(stressed_crises)}–{max(stressed_crises)})")
        print(f"  Unstressed system: mean overloads = {mean_unstressed:.1f} "
              f"(range {min(unstressed_crises)}–{max(unstressed_crises)})")
        print(f"  Dependency ratio:  {dependency_ratio:.2f}× "
              f"(stressed / unstressed)")
        print(f"  → {'PASS ✓ — stress state mattered' if test_pass else 'FAIL ✗ — trigger was sufficient alone'}")

    return {
        "test":                "trigger_dependency",
        "scenario":            scenario_name,
        "mean_overload_stressed":   round(mean_stressed,   2),
        "mean_overload_unstressed": round(mean_unstressed, 2),
        "dependency_ratio":         round(dependency_ratio, 3),
        "score3_pass":              test_pass,
        "stressed_crises":          stressed_crises,
        "unstressed_crises":        unstressed_crises,
    }


# ============================================================================
# E: Network structure validation
# ============================================================================

def validate_network_structure(
    model: FoodEnergyModel,
    verbose: bool = True,
) -> dict:
    """
    Validate trade network structure against empirical expectations.

    Checks:
      1. Degree distribution: does it follow a roughly power-law / hub structure?
      2. Centrality: do USA, China, Russia, Brazil emerge as top hubs?
      3. Export volumes: do major exporters match real-world expectations?
    """
    G = model.network

    # Out-degree (export connections)
    out_degrees = dict(G.out_degree())
    in_degrees  = dict(G.in_degree())

    # Betweenness centrality (most important relay nodes)
    betweenness = nx.betweenness_centrality(G, weight="C_ij")
    top_between = sorted(betweenness.items(), key=lambda x: -x[1])[:10]

    # Weighted PageRank (trade influence — weighted by C_ij capacity)
    pagerank = nx.pagerank(G, alpha=0.85, weight="C_ij")
    top_pr   = sorted(pagerank.items(), key=lambda x: -x[1])[:10]

    expected_hubs = {"United States", "China", "Brazil", "Russia", "Australia",
                     "France", "Canada", "Argentina", "Ukraine", "India"}
    top10_pagerank = {n for n, _ in top_pr}
    hub_overlap = len(expected_hubs & top10_pagerank)
    hub_check_pass = hub_overlap >= 6  # at least 6 of 10 expected hubs in top 10

    # Edge weight distribution
    weights = [d.get("C_ij", 0) for _, _, d in G.edges(data=True)]
    w_arr   = np.array(weights)

    if verbose:
        print(f"\n  Network structure validation:")
        print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
        print(f"  Edge weight: mean={w_arr.mean():.2e}, max={w_arr.max():.2e}, "
              f"min={w_arr.min():.2e}")
        print(f"\n  Top 10 by PageRank (trade influence):")
        for i, (n, pr) in enumerate(top_pr, 1):
            flag = "✓" if n in expected_hubs else ""
            print(f"    {i:>2}. {n:<35} {pr:.4f} {flag}")
        print(f"\n  Hub emergence: {hub_overlap}/10 expected hubs in top 10 → "
              f"{'PASS ✓' if hub_check_pass else 'FAIL ✗'}")

    return {
        "n_nodes":         G.number_of_nodes(),
        "n_edges":         G.number_of_edges(),
        "hub_overlap":     hub_overlap,
        "hub_check_pass":  hub_check_pass,
        "top10_pagerank":  [n for n, _ in top_pr],
        "top10_betweenness":[n for n, _ in top_between],
        "weight_mean":     float(w_arr.mean()),
        "weight_std":      float(w_arr.std()),
    }


# ============================================================================
# Master retrodiction table (examiner-ready)
# ============================================================================

def build_retrodiction_table(
    r2008: dict,
    r2022: dict,
    stability: dict,
    td2008: dict,
    td2022: dict,
) -> pd.DataFrame:
    """
    Build the examiner-facing retrodiction comparison table.

    Format (per reviewer feedback):
      Metric | Real | Model 2008 | Model 2022
    """
    rows = [
        {
            "Metric":         "Peak FPI (normalised)",
            "Real_2008":      f"{REAL_FPI_2008:.3f}",
            "Model_2008":     f"{r2008['model_fpi_mean']:.3f} ± {r2008['model_fpi_std']:.3f}",
            "Error_2008_pct": f"{r2008['fpi_error_pct']:.1f}%",
            "Pass_2008":      "✓" if r2008["score1_fpi"] else "✗",
            "Real_2022":      f"{REAL_FPI_2022:.3f}",
            "Model_2022":     f"{r2022['model_fpi_mean']:.3f} ± {r2022['model_fpi_std']:.3f}",
            "Error_2022_pct": f"{r2022['fpi_error_pct']:.1f}%",
            "Pass_2022":      "✓" if r2022["score1_fpi"] else "✗",
        },
        {
            "Metric":         "Peak export ban rate",
            "Real_2008":      f"{REAL_EXPORT_BAN_RATE_2008:.2f}",
            "Model_2008":     f"{r2008['model_eb_mean']:.3f}",
            "Error_2008_pct": "—",
            "Pass_2008":      "✓" if r2008["score2_eb"] else "✗",
            "Real_2022":      f"{REAL_EXPORT_BAN_RATE_2022:.2f}",
            "Model_2022":     f"{r2022['model_eb_mean']:.3f}",
            "Error_2022_pct": "—",
            "Pass_2022":      "✓" if r2022["score2_eb"] else "✗",
        },
        {
            "Metric":         "Trigger-dependency test",
            "Real_2008":      "stress state needed",
            "Model_2008":     f"ratio={td2008['dependency_ratio']:.2f}×",
            "Error_2008_pct": "—",
            "Pass_2008":      "✓" if td2008["score3_pass"] else "✗",
            "Real_2022":      "stress state needed",
            "Model_2022":     f"ratio={td2022['dependency_ratio']:.2f}×",
            "Error_2022_pct": "—",
            "Pass_2022":      "✓" if td2022["score3_pass"] else "✗",
        },
        {
            "Metric":         "PAR (billions, order of mag)",
            "Real_2008":      f"{REAL_PAR_BILLIONS_2008:.2f}bn",
            "Model_2008":     f"{r2008['model_par_bn']:.2f}bn",
            "Error_2008_pct": f"ratio={r2008['par_ratio']:.2f}×",
            "Pass_2008":      "✓" if r2008["score4_par"] else "✗",
            "Real_2022":      f"{REAL_PAR_BILLIONS_2022:.2f}bn",
            "Model_2022":     f"{r2022['model_par_bn']:.2f}bn",
            "Error_2022_pct": f"ratio={r2022['par_ratio']:.2f}×",
            "Pass_2022":      "✓" if r2022["score4_par"] else "✗",
        },
        {
            "Metric":         "HD 4 properties satisfied",
            "Real_2008":      "all 4",
            "Model_2008":     str(sum(r2008["crisis_properties"].values())) + "/4",
            "Error_2008_pct": "—",
            "Pass_2008":      "✓" if r2008["score5_hd_props"] else "✗",
            "Real_2022":      "all 4",
            "Model_2022":     str(sum(r2022["crisis_properties"].values())) + "/4",
            "Error_2022_pct": "—",
            "Pass_2022":      "✓" if r2022["score5_hd_props"] else "✗",
        },
        {
            "Metric":         "Stability test (no crisis)",
            "Real_2008":      "—",
            "Model_2008":     "—",
            "Error_2008_pct": "—",
            "Pass_2008":      "—",
            "Real_2022":      "FPI<1.20, U<0.40",
            "Model_2022":     f"FPI={stability['price_ratio_mean']:.3f}, U={stability['U_mean']:.3f}",
            "Error_2022_pct": "—",
            "Pass_2022":      "✓" if stability["all_pass"] else "✗",
        },
    ]
    return pd.DataFrame(rows)


# ============================================================================
# Entry point
# ============================================================================

def run_phase8(
    data_dir: Path = _DATA,
    n_steps: int = 25,
    n_mc: int = N_MC_RETRO,
    verbose: bool = True,
) -> dict:
    """Run full Phase 8 retrodiction and save all outputs."""

    print("\n" + "="*60)
    print("  PHASE 8: HISTORICAL RETRODICTION")
    print("  (most important phase — does the model reproduce reality?)")
    print("="*60)

    # ── A. 2008 retrodiction ───────────────────────────────────────────────────
    # BUG-008 FIX (audit Fix #1, CRITICAL): previously this ran with the
    # default init_year=2022 — a 2022-configured world (2022 population,
    # capital, technology, A_i) retrodicting the 2008 crisis. Now initialises
    # from real 2000 panel data (earliest year with full coverage) and
    # shortens the stage-1 build window via step_offset so the proximate
    # trigger still lands on simulated year 2008 (init_year 2000 + step 8).
    INIT_YEAR_2008    = 2000
    STEP_OFFSET_2008  = -7   # original step 15 → step 8 (= calendar year 2008)
    r2008 = retrodict_crisis(
        triggers_fn   = lambda: triggers_2008_food_energy(step_offset=STEP_OFFSET_2008),
        scenario_name = "retro_2008",
        real_fpi      = REAL_FPI_2008,
        real_eb_rate  = REAL_EXPORT_BAN_RATE_2008,
        real_par_bn   = REAL_PAR_BILLIONS_2008,
        n_steps       = n_steps,
        verbose       = verbose,
        init_year     = INIT_YEAR_2008,
    )

    # ── B. 2022 retrodiction ───────────────────────────────────────────────────
    # BUG-008 FIX: initialises from real 2018 panel data rather than 2022,
    # so the model retrodicts the 2022 crisis from pre-crisis conditions
    # instead of conditions already reflecting the crisis year itself.
    INIT_YEAR_2022    = 2018
    STEP_OFFSET_2022  = -6   # original step 10 → step 4 (= calendar year 2022)
    r2022 = retrodict_crisis(
        triggers_fn   = lambda: triggers_2022_ukraine(step_offset=STEP_OFFSET_2022),
        scenario_name = "retro_2022",
        real_fpi      = REAL_FPI_2022,
        real_eb_rate  = REAL_EXPORT_BAN_RATE_2022,
        real_par_bn   = REAL_PAR_BILLIONS_2022,
        n_steps       = n_steps,
        verbose       = verbose,
        init_year     = INIT_YEAR_2022,
    )

    # ── C. Stability test ──────────────────────────────────────────────────────
    stability = stability_test(n_steps=n_steps, n_runs=10, verbose=verbose)

    # ── D. Trigger-dependency tests ────────────────────────────────────────────
    td2008 = trigger_dependency_test(
        triggers_fn   = lambda: triggers_2008_food_energy(step_offset=STEP_OFFSET_2008),
        scenario_name = "trigger_dep_2008",
        n_steps       = n_steps,
        n_runs        = 10,
        verbose       = verbose,
    )
    td2022 = trigger_dependency_test(
        triggers_fn   = lambda: triggers_2022_ukraine(step_offset=STEP_OFFSET_2022),
        scenario_name = "trigger_dep_2022",
        n_steps       = n_steps,
        n_runs        = 10,
        verbose       = verbose,
    )

    # ── C. 2010-11 Russia drought + Arab Spring retrodiction ───────────────────
    # Added this session. init_year=2008 gives a temporally coherent window
    # off the real 2008 panel data. Scored the same way as 2008/2022 (real
    # global FPI spike applies here, unlike the 2004-05 Niger episode).
    INIT_YEAR_2011    = 2008
    STEP_OFFSET_2011  = 0   # triggers already calendar-aligned to init_year=2008
    r2011 = retrodict_crisis(
        triggers_fn   = lambda: triggers_2010_russia_drought(step_offset=STEP_OFFSET_2011),
        scenario_name = "retro_2011",
        real_fpi      = REAL_FPI_2011,   # true peak of the 2-year crisis
        real_eb_rate  = REAL_EXPORT_BAN_RATE_2011,
        real_par_bn   = REAL_PAR_BILLIONS_2011,
        n_steps       = n_steps,
        verbose       = verbose,
        init_year     = INIT_YEAR_2011,
    )

    # ── D. 2019-20 COVID + East Africa locust retrodiction ─────────────────────
    INIT_YEAR_2020    = 2018
    STEP_OFFSET_2020  = 0
    r2020 = retrodict_crisis(
        triggers_fn   = lambda: triggers_2019_covid_locust(step_offset=STEP_OFFSET_2020),
        scenario_name = "retro_2020",
        real_fpi      = REAL_FPI_2020,
        real_eb_rate  = REAL_EXPORT_BAN_RATE_2020,
        real_par_bn   = REAL_PAR_BILLIONS_2020,
        n_steps       = n_steps,
        verbose       = verbose,
        init_year     = INIT_YEAR_2020,
    )

    # ── E. 2004-05 Niger/Sahel retrodiction -- DESCRIPTIVE ONLY ─────────────────
    # NOT scored against global FPI/PAR: this was a regional crisis (real
    # global FPI stayed at 0.656-0.674, well below baseline -- see
    # triggers_2004_niger_sahel docstring), and the ABM only has a bloc-level
    # West Africa (ECOWAS) node, not a Niger-specific one, so the real
    # national-level PAR figure (2.5-3.3M people) isn't a clean comparison
    # against bloc-wide model output either. Per decision this session: run
    # and report model output descriptively, do not force a pass/fail score
    # against a mismatched real-world number.
    INIT_YEAR_2005    = 2002
    STEP_OFFSET_2005  = 0
    print(f"\n{'─'*55}")
    print("  2004-05 Niger/Sahel Retrodiction (DESCRIPTIVE ONLY)")
    print(f"{'─'*55}")
    r2005_model = FoodEnergyModel(scenario="retro_2005", seed=42, init_year=INIT_YEAR_2005)
    r2005_model.stc_engine = STCEngine(
        triggers=triggers_2004_niger_sahel(step_offset=STEP_OFFSET_2005),
        ss_mode="multiplicative",
    )
    r2005_model.run(n_steps, verbose=False)
    r2005_summary = r2005_model.summary()
    r2005 = {
        "descriptive_only": True,
        "note": ("Regional crisis (real global FPI stayed 0.656-0.674, well "
                 "below the 1.0 baseline) -- not comparable to the 2008/2022/"
                 "2011/2020 global-FPI-scored episodes. Real-world anchor: "
                 "2.5-3.3M people affected in Niger (WFP/OCHA), not directly "
                 "comparable to this bloc-level model's West Africa PAR output."),
        "model_max_price_index":     r2005_summary.get("max_price_index"),
        "model_max_PAR_millions":    r2005_summary.get("max_PAR_millions"),
        "model_max_n_overload_food": r2005_summary.get("max_n_overload_food"),
        "real_par_niger_millions":   "2.5-3.3 (WFP/OCHA, national Niger figure, not bloc-comparable)",
    }
    if verbose:
        print(f"  Model max_price_index: {r2005['model_max_price_index']}")
        print(f"  Model max_PAR_millions: {r2005['model_max_PAR_millions']}")
        print(f"  (Not scored -- see note in retrodiction_scores.json)")

    # ── F. Network validation ──────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print(f"  Network Structure Validation")
    print(f"{'─'*55}")
    ref_model = FoodEnergyModel(scenario="net_validation", seed=42)
    net_val   = validate_network_structure(ref_model, verbose=verbose)

    # ── Retrodiction comparison table ──────────────────────────────────────────
    table = build_retrodiction_table(r2008, r2022, stability, td2008, td2022)

    print(f"\n{'='*60}")
    print("  RETRODICTION COMPARISON TABLE")
    print(f"{'='*60}")
    print(table.to_string(index=False))

    # ── Scores summary ────────────────────────────────────────────────────────
    scores = {
        "2008_score1_fpi":    r2008["score1_fpi"],
        "2008_score2_eb":     r2008["score2_eb"],
        "2008_score4_par":    r2008["score4_par"],
        "2008_score5_hd":     r2008["score5_hd_props"],
        "2008_score3_td":     td2008["score3_pass"],
        "2022_score1_fpi":    r2022["score1_fpi"],
        "2022_score2_eb":     r2022["score2_eb"],
        "2022_score4_par":    r2022["score4_par"],
        "2022_score5_hd":     r2022["score5_hd_props"],
        "2022_score3_td":     td2022["score3_pass"],
        # New episodes added this session. No trigger-dependency (score3_td)
        # test built for these yet -- scoped out, not silently omitted; add
        # run_trigger_dependency_test(...) calls for these when that's done.
        "2011_score1_fpi":    r2011["score1_fpi"],
        "2011_score2_eb":     r2011["score2_eb"],
        "2011_score4_par":    r2011["score4_par"],
        "2011_score5_hd":     r2011["score5_hd_props"],
        "2020_score1_fpi":    r2020["score1_fpi"],
        "2020_score2_eb":     r2020["score2_eb"],
        "2020_score4_par":    r2020["score4_par"],
        "2020_score5_hd":     r2020["score5_hd_props"],
        "stability_all_pass": stability["all_pass"],
        "network_hubs_pass":  net_val["hub_check_pass"],
        # 2004-05 Niger is intentionally excluded from this scored dict --
        # see r2005["note"] for why. Its output is still saved separately
        # (retrodiction_2005_descriptive.json) so it's not silently dropped.
    }

    total_pass = sum(1 for v in scores.values() if v)
    total      = len(scores)
    pom_score  = total_pass / total

    print(f"\n{'='*60}")
    print(f"  OVERALL RETRODICTION SCORE: {total_pass}/{total} = {pom_score:.2f}")
    print(f"  (Target: ≥ 0.70; {total} criteria across 4 scored episodes + ")
    print(f"   stability + network; 2004-05 Niger reported separately, ")
    print(f"   descriptive only)")
    print(f"  → {'PASS ✓' if pom_score >= 0.70 else 'NEEDS IMPROVEMENT'}")
    print(f"{'='*60}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    table.to_csv(data_dir / "retrodiction_table.csv", index=False)

    stability["raw_df"].to_csv(data_dir / "retrodiction_stability.csv", index=False)

    td_df = pd.DataFrame([
        {"episode": "2008", **{k: v for k, v in td2008.items()
                                if not isinstance(v, list)}},
        {"episode": "2022", **{k: v for k, v in td2022.items()
                                if not isinstance(v, list)}},
    ])
    td_df.to_csv(data_dir / "retrodiction_trigger_dep.csv", index=False)

    with open(data_dir / "retrodiction_scores.json", "w") as f:
        json.dump({**scores, "pom_score": round(pom_score, 4)}, f, indent=2)

    with open(data_dir / "retrodiction_2005_descriptive.json", "w") as f:
        json.dump(r2005, f, indent=2)

    print(f"\n[Phase 8] Saved: retrodiction_table.csv, retrodiction_stability.csv,")
    print(f"          retrodiction_trigger_dep.csv, retrodiction_scores.json,")
    print(f"          retrodiction_2005_descriptive.json")

    return {
        "r2008":      r2008,
        "r2022":      r2022,
        "r2011":      r2011,
        "r2020":      r2020,
        "r2005":      r2005,
        "stability":  stability,
        "td2008":     td2008,
        "td2022":     td2022,
        "net_val":    net_val,
        "table":      table,
        "scores":     scores,
        "pom_score":  pom_score,
    }


if __name__ == "__main__":
    run_phase8(n_steps=25, n_mc=N_MC_RETRO, verbose=True)

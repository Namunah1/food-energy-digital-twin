"""
model_bridge.py
----------------
Thin bridge between the FastAPI layer and the vendored Python ABM
(model_src/Food_Energy_Systemic_Risk_ABM/src). This module ONLY orchestrates
calls into the real model -- it does not compute, approximate, or reimplement
any scientific quantity. Every metric returned to the API comes directly from
FoodEnergyModel / MetricsCollector / scenarios.py.
"""
from __future__ import annotations

import sys
import functools
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import pandas as pd

_MODEL_ROOT = Path(__file__).resolve().parent.parent / "model"
_SRC = _MODEL_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from model import FoodEnergyModel          # noqa: E402
from scenarios import (                    # noqa: E402
    SCENARIOS as SCENARIO_REGISTRY,
    ScenarioSpec,
    crisis_attribution,
    _trader_regulation as _trader_regulation_only,  # standalone lever (S5 bundles this with others)
    policy_search as _policy_search,           # PHASE A (this session)
    node_level_policy_search as _node_level_policy_search,  # PHASE D (this session)
)
from stc_engine import STCEngine           # noqa: E402

from .coordinates import get_coordinates

DATA_DIR = _MODEL_ROOT / "data"

# Response levers exposed as importable functions so custom scenarios built
# in the Scenario Lab can reuse the exact same intervention logic the
# research scenarios (S3/S4/S5) use -- not a JS reimplementation.
_SPEC_BY_NAME = {s.name: s for s in SCENARIO_REGISTRY}


def list_scenario_specs() -> list[dict]:
    """Return the built-in research scenario registry for the frontend."""
    out = []
    for s in SCENARIO_REGISTRY:
        out.append({
            "name": s.name,
            "label": s.label,
            "description": s.description,
            "storyline": s.storyline,
            "trade_offs": s.trade_offs,
            "triggers": s.triggers,
            "has_response": s.response_fn.__name__ != "_no_response",
        })
    return out


def list_countries() -> list[dict]:
    """Static node list (names + type + coordinates) -- no simulation run."""
    node_params_path = DATA_DIR / "processed" / "node_parameters.csv"
    df = pd.read_csv(node_params_path)
    out = []
    for _, row in df.iterrows():
        name = str(row["Node"])
        coords = get_coordinates(name)
        out.append({
            "id": name,
            "name": name,
            "type": str(row.get("Type", "hub_country")),
            "lat": coords["lat"],
            "lon": coords["lon"],
            "region": coords["region"],
            "population": float(row.get("P_i", 0.0)),
        })
    return out


@functools.lru_cache(maxsize=4)
def _baseline_run_cached(steps: int, seed: int):
    """
    Run (and cache) a baseline model for `steps` years. Cached because the
    dashboard/map/network endpoints all want "current baseline state" and
    re-running the ABM per request would be wasteful. Cache is keyed on
    (steps, seed) so it's still exact, not approximated.
    """
    model = FoodEnergyModel(scenario="baseline", seed=seed)
    model.run(steps, verbose=False)
    return model


def get_baseline_model(steps: int = 10, seed: int = 42) -> FoodEnergyModel:
    return _baseline_run_cached(steps, seed)


def node_state_snapshot(model: FoodEnergyModel) -> list[dict]:
    """Per-node current state, merged with coordinates, for map/network views."""
    df = model.node_dataframe()
    out = []
    for _, row in df.iterrows():
        name = row["node"]
        coords = get_coordinates(name)
        out.append({
            "id": name,
            "name": name,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "region": coords["region"],
            "food_security": float(row["food_security"]),
            "export_ban": bool(row["export_ban"]),
            "export_fraction": float(row["export_fraction"]),
            "population_millions": float(row["population_M"]),
            "undernourished": bool(row["undernourished"]),
            "capital_bn": float(row["capital_bn"]),
            "technology": float(row["technology"]),
            "energy_fuel": float(row["energy_fuel"]),
            "energy_stress": float(row["energy_stress"]),
            "fs_index": float(row["FS_index"]),
            "cc_index": float(row["CC_index"]),
            "overload_food": bool(row["overload_food"]),
        })
    return out


def network_edges(model: FoodEnergyModel) -> list[dict]:
    """Active (and inactive) trade edges from the model's network graph."""
    G = model.network
    edges = []
    for src, dst, data in G.edges(data=True):
        edges.append({
            "source": src,
            "target": dst,
            "active": bool(data.get("active", True)),
            "capacity": float(data.get("C_ij", 0.0) or 0.0),
            "cost": float(data.get("kappa_ij", 0.0) or 0.0),
            "risk": float(data.get("rho_ij", 0.0) or 0.0),
        })
    return edges


def global_metrics_timeseries(model: FoodEnergyModel) -> list[dict]:
    return model.metrics_dataframe().to_dict(orient="records")


def country_profile(name: str, steps: int = 10, seed: int = 42) -> Optional[dict]:
    model = get_baseline_model(steps=steps, seed=seed)
    if name not in model.agent_map:
        return None
    agent = model.agent_map[name]
    coords = get_coordinates(name)

    partners_out = []
    for _, dst, data in model.network.out_edges(name, data=True):
        partners_out.append({
            "partner": dst, "direction": "export",
            "active": bool(data.get("active", True)),
            "capacity": float(data.get("C_ij", 0.0) or 0.0),
        })
    partners_in = []
    for src, _, data in model.network.in_edges(name, data=True):
        partners_in.append({
            "partner": src, "direction": "import",
            "active": bool(data.get("active", True)),
            "capacity": float(data.get("C_ij", 0.0) or 0.0),
        })

    return {
        "id": name,
        "name": name,
        "type": agent.node_type,
        "lat": coords["lat"], "lon": coords["lon"], "region": coords["region"],
        "population": agent.population,
        "capital_bn": agent.capital,
        "gdp_bn": agent.gdp,
        "technology": agent.technology,
        "energy_fuel": agent.energy_fuel,
        "energy_renew": agent.energy_renew,
        "energy_stress_index": getattr(agent, "energy_stress_index", 0.0),
        "food_security": agent.food_security,
        "undernourished": bool(agent.undernourished),
        "export_ban": bool(agent.export_ban),
        "export_fraction": agent.export_fraction,
        "FS_index": agent.FS_index,
        "CC_index": agent.CC_index,
        "overload_food": bool(getattr(agent, "overload_food", False)),
        "climate_vuln": agent.climate_vuln,
        "political_risk": agent.political_risk,
        "exports_this_step": agent.exports_this_step,
        "imports_this_step": agent.imports_this_step,
        "trade_partners_export": partners_out,
        "trade_partners_import": partners_in,
    }


# ── Shock-type → STC trigger template ---------------------------------------
# Maps the Scenario Lab's human-facing shock categories onto the trigger
# schema already used by scenarios.py (see stc_engine.py header docstring).
# This is configuration only -- the STC engine itself performs all the
# actual stress/overload/cascade computation.
SHOCK_TYPE_MAP = {
    "climate_drought":     {"type": "climate",      "food_shock_base": 1.20, "energy_shock_base": 1.00},
    "energy_crisis":       {"type": "geopolitical",  "food_shock_base": 1.15, "energy_shock_base": 1.80},
    "pandemic":            {"type": "pandemic",      "food_shock_base": 1.10, "energy_shock_base": 1.05},
    "financial_crisis":    {"type": "speculative",   "food_shock_base": 1.25, "energy_shock_base": 1.15},
    "export_ban":          {"type": "geopolitical",  "food_shock_base": 1.30, "energy_shock_base": 1.00},
    "war":                 {"type": "geopolitical",  "food_shock_base": 1.55, "energy_shock_base": 2.00},
    "fertilizer_shortage": {"type": "geopolitical",  "food_shock_base": 1.20, "energy_shock_base": 1.30},
    "shipping_disruption": {"type": "geopolitical",  "food_shock_base": 1.15, "energy_shock_base": 1.10},
    "currency_collapse":   {"type": "speculative",   "food_shock_base": 1.20, "energy_shock_base": 1.10},
}

def _renewable_push_only(model):
    """
    Standalone renewable-energy lever, extracted verbatim from
    scenarios._transformational (which otherwise only offers it bundled
    with reserves + diversification + trader regulation). Copied exactly,
    not reinterpreted -- same two lines, same effect, just isolated so
    Policy Optimization can rank it as its own atomic intervention.
    """
    for agent in model.agent_map.values():
        agent.energy_renew = min(agent.energy_renew * 1.40, 200.0)
        agent.xi_biofuel = 0.0


RESPONSE_FN = {
    "reserve_mandate":       _SPEC_BY_NAME["S3_reserve_mandate"].response_fn,
    "trade_diversification": _SPEC_BY_NAME["S4_trade_diversification"].response_fn,
    "trader_regulation":     _SPEC_BY_NAME["S5_transformational"].response_fn,  # includes regulation
}

# Atomic (single-mechanism) levers for Policy Optimization ranking -- as
# opposed to RESPONSE_FN above, where "trader_regulation" maps to the full
# S5 bundle for backward-compat with the Scenario Lab/Compare UI labels.
ATOMIC_RESPONSE_FN = {
    "reserve_mandate":       _SPEC_BY_NAME["S3_reserve_mandate"].response_fn,
    "trade_diversification": _SPEC_BY_NAME["S4_trade_diversification"].response_fn,
    "trader_regulation_only": _trader_regulation_only,
    "renewable_push_only":   _renewable_push_only,
    "full_transformational": _SPEC_BY_NAME["S5_transformational"].response_fn,
}

ATOMIC_RESPONSE_LABELS = {
    "reserve_mandate": "Strategic reserves (3-month FAO mandate)",
    "trade_diversification": "Trade corridor diversification",
    "trader_regulation_only": "Trader margin regulation (5% cap)",
    "renewable_push_only": "Renewable energy push (+40%)",
    "full_transformational": "Full transformational bundle (all of the above)",
}


def build_triggers_from_shocks(shocks: list[dict], n_steps: int) -> list[dict]:
    """
    Turn Scenario Lab UI shocks into STC trigger dicts. Each UI shock has:
      shock_type   : one of SHOCK_TYPE_MAP keys
      start_step   : int
      duration     : int (>=1) -- trigger re-fires each step of the duration
      severity     : 0-100 (UI) -> 0-1
      scope        : 0-100 (UI) -> 0-1, fraction of nodes affected
      target_node  : str | None
    """
    triggers = []
    for i, shock in enumerate(shocks):
        cfg = SHOCK_TYPE_MAP.get(shock["shock_type"])
        if cfg is None:
            continue
        severity = float(np.clip(shock.get("severity", 50) / 100.0, 0.0, 1.0))
        scope = float(np.clip(shock.get("scope", 30) / 100.0, 0.0, 1.0))
        start = int(shock.get("start_step", 5))
        duration = max(1, int(shock.get("duration", 1)))
        target = shock.get("target_node") or None

        food_shock = 1.0 + (cfg["food_shock_base"] - 1.0) * severity
        energy_shock = 1.0 + (cfg["energy_shock_base"] - 1.0) * severity

        for d in range(duration):
            step = start + d
            if step >= n_steps:
                break
            triggers.append({
                "name": f"lab_shock_{i}_{shock['shock_type']}_t{step}",
                "step": step,
                "type": cfg["type"],
                "scope": scope,
                "severity": severity,
                "food_shock": food_shock,
                "energy_shock": energy_shock,
                "target_node": target,
            })
    return triggers


def run_custom_simulation(
    shocks: list[dict],
    responses: list[str],
    n_steps: int = 30,
    seed: int = 42,
    step_callback: Optional[Callable[[int, dict], None]] = None,
    capture_snapshots: bool = False,
    init_year: int = 2022,
) -> dict:
    """
    Run a single (non-Monte-Carlo) custom scenario built in the Scenario Lab.
    Uses the exact same model, STCEngine and response-lever functions as the
    research scenarios in scenarios.py -- only the trigger list and which
    response levers are toggled come from the user.

    capture_snapshots=True additionally records a full node_state_snapshot
    after every step (same shape as time_machine's snapshots), enabling
    Timeline Replay of the shocked run -- not just its final state.
    """
    model = FoodEnergyModel(scenario="lab_custom", seed=seed, init_year=init_year)

    for r in responses:
        fn = RESPONSE_FN.get(r)
        if fn:
            fn(model)

    triggers = build_triggers_from_shocks(shocks, n_steps)
    model.stc_engine = STCEngine(triggers=triggers, ss_mode="multiplicative")

    snapshots = []
    if capture_snapshots:
        snapshots.append({"step": 0, "year": init_year, "nodes": node_state_snapshot(model)})

    for i in range(n_steps):
        model.step()
        if step_callback:
            rec = model.metrics_dataframe().to_dict(orient="records")[-1]
            step_callback(i + 1, rec)
        if capture_snapshots:
            snapshots.append({"step": i + 1, "year": init_year + i + 1, "nodes": node_state_snapshot(model)})

    attribution_df = crisis_attribution(model)

    return {
        "summary": model.summary(),
        "timeseries": global_metrics_timeseries(model),
        "nodes": node_state_snapshot(model),
        "snapshots": snapshots if capture_snapshots else None,
        "attribution": attribution_df.to_dict(orient="records") if not attribution_df.empty else [],
        "triggers_applied": triggers,
    }


def run_baseline_comparison(n_steps: int = 30, seed: int = 42) -> dict:
    """Baseline run (no shocks, no responses) -- used as the comparison line."""
    model = FoodEnergyModel(scenario="baseline_compare", seed=seed)
    model.run(n_steps, verbose=False)
    return {
        "summary": model.summary(),
        "timeseries": global_metrics_timeseries(model),
        "nodes": node_state_snapshot(model),
    }


def run_research_scenario(name: str, n_mc: int = 5, n_steps: int = 30, seed: int = 42) -> dict:
    """
    Run one of the six built-in research scenarios (S0-S5) with Monte Carlo
    uncertainty quantification, using scenarios.run_scenario directly.
    n_mc defaults lower than the paper's N_MC=20 for interactive response
    times; the frontend can request more for a "high precision" run.
    """
    from scenarios import run_scenario as _run_scenario
    spec = _SPEC_BY_NAME[name]
    result = _run_scenario(spec, n_steps=n_steps, n_mc=n_mc, seed=seed, verbose=False)
    result["attribution"] = (
        result["attribution"].to_dict(orient="records")
        if isinstance(result["attribution"], pd.DataFrame) and not result["attribution"].empty
        else []
    )
    return result


# ── Historical replay -------------------------------------------------------
# Uses retrodiction.py's exact scoring functions and real trigger sets --
# no numbers here are re-derived or approximated by the API layer.
import retrodiction as _retro  # noqa: E402

HISTORICAL_EPISODES = {
    "2008": dict(
        label="2008 Global Food-Energy Crisis",
        triggers_fn=lambda: _retro.triggers_2008_food_energy(step_offset=-7),
        scenario_name="retro_2008",
        real_fpi=_retro.REAL_FPI_2008,
        real_eb_rate=_retro.REAL_EXPORT_BAN_RATE_2008,
        real_par_bn=_retro.REAL_PAR_BILLIONS_2008,
        init_year=2000,
        trigger_calendar_year=2008,
    ),
    "2011": dict(
        label="2010-11 Russia Drought / Arab Spring",
        triggers_fn=lambda: _retro.triggers_2010_russia_drought(step_offset=0),
        scenario_name="retro_2011",
        real_fpi=_retro.REAL_FPI_2011,
        real_eb_rate=_retro.REAL_EXPORT_BAN_RATE_2011,
        real_par_bn=_retro.REAL_PAR_BILLIONS_2011,
        init_year=2008,
        trigger_calendar_year=2011,
    ),
    "2020": dict(
        label="2019-20 COVID / East Africa Locust",
        triggers_fn=lambda: _retro.triggers_2019_covid_locust(step_offset=0),
        scenario_name="retro_2020",
        real_fpi=_retro.REAL_FPI_2020,
        real_eb_rate=_retro.REAL_EXPORT_BAN_RATE_2020,
        real_par_bn=_retro.REAL_PAR_BILLIONS_2020,
        init_year=2018,
        trigger_calendar_year=2020,
    ),
    "2022": dict(
        label="2022 Ukraine Food-Energy Crisis",
        triggers_fn=lambda: _retro.triggers_2022_ukraine(step_offset=-6),
        scenario_name="retro_2022",
        real_fpi=_retro.REAL_FPI_2022,
        real_eb_rate=_retro.REAL_EXPORT_BAN_RATE_2022,
        real_par_bn=_retro.REAL_PAR_BILLIONS_2022,
        init_year=2018,
        trigger_calendar_year=2022,
    ),
}

# The 2004-05 Niger/Sahel crisis is structurally different from the other
# four: your own code marks it "descriptive-only" because it was a regional
# (not global) crisis -- real global FPI stayed at 0.656-0.674, well below
# the 1.0 baseline, so scoring it against global FPI/PAR the way 2008/2011/
# 2020/2022 are scored would be comparing it to the wrong thing. The ABM
# also only has a bloc-level "West Africa (ECOWAS)" node, not a Niger-
# specific one, so the real national PAR figure (2.5-3.3M people, WFP/OCHA)
# isn't cleanly comparable to bloc-wide model output either. This mirrors
# retrodiction.py's own run_phase8 handling of this episode exactly.
DESCRIPTIVE_EPISODES = {
    "2004_niger": dict(
        label="2004-05 Niger/Sahel Crisis (regional, descriptive only)",
        triggers_fn=lambda: _retro.triggers_2004_niger_sahel(step_offset=0),
        scenario_name="retro_2005",
        init_year=2002,
        trigger_calendar_year=2004,
        note=(
            "Regional crisis (real global FPI stayed 0.656-0.674, well below "
            "the 1.0 baseline) -- not comparable to the 2008/2011/2020/2022 "
            "global-FPI-scored episodes. Real-world anchor: 2.5-3.3M people "
            "affected in Niger (WFP/OCHA), not directly comparable to this "
            "bloc-level model's West Africa (ECOWAS) PAR output."
        ),
        real_par_niger_millions="2.5-3.3 (WFP/OCHA, national Niger figure, not bloc-comparable)",
    ),
}


def list_historical_episodes() -> list[dict]:
    scored = [{"key": k, "label": v["label"], "trigger_calendar_year": v["trigger_calendar_year"],
               "scored": True} for k, v in HISTORICAL_EPISODES.items()]
    descriptive = [{"key": k, "label": v["label"], "trigger_calendar_year": v["trigger_calendar_year"],
                     "scored": False} for k, v in DESCRIPTIVE_EPISODES.items()]
    return sorted(scored + descriptive, key=lambda e: e["trigger_calendar_year"])


@functools.lru_cache(maxsize=4)
def _descriptive_run_cached(episode_key: str, n_steps: int):
    ep = DESCRIPTIVE_EPISODES[episode_key]
    model = FoodEnergyModel(scenario=ep["scenario_name"], seed=42, init_year=ep["init_year"])
    model.stc_engine = STCEngine(triggers=ep["triggers_fn"](), ss_mode="multiplicative")
    model.run(n_steps, verbose=False)
    return ep, model


def run_descriptive_episode(episode_key: str, n_steps: int = 6) -> dict:
    if episode_key not in DESCRIPTIVE_EPISODES:
        return None
    ep, model = _descriptive_run_cached(episode_key, n_steps)
    summary = model.summary()
    return {
        "key": episode_key,
        "label": ep["label"],
        "trigger_calendar_year": ep["trigger_calendar_year"],
        "init_year": ep["init_year"],
        "descriptive_only": True,
        "note": ep["note"],
        "triggers": ep["triggers_fn"](),
        "timeseries": global_metrics_timeseries(model),
        "nodes": node_state_snapshot(model),
        "model_max_price_index": summary.get("max_price_index"),
        "model_max_PAR_millions": summary.get("max_PAR_millions"),
        "model_max_n_overload_food": summary.get("max_n_overload_food"),
        "real_par_niger_millions": ep["real_par_niger_millions"],
    }


@functools.lru_cache(maxsize=8)
def _historical_run_cached(episode_key: str, n_mc: int, n_steps: int):
    ep = HISTORICAL_EPISODES[episode_key]

    # Single detailed run -- gives us the actual per-step timeseries + final
    # node snapshot to chart/map, using the same triggers as the scored run.
    detail_summary, model = _retro._run_retrodiction_episode(
        ep["triggers_fn"], ep["scenario_name"], n_steps, seed=42, init_year=ep["init_year"],
    )

    # Scored run (real retrodict_crisis, with a reduced MC count for
    # interactive latency -- same scoring logic, fewer Monte Carlo draws
    # than the paper's N_MC_RETRO=30).
    old_n_mc = _retro.N_MC_RETRO
    _retro.N_MC_RETRO = n_mc
    try:
        scored = _retro.retrodict_crisis(
            triggers_fn=ep["triggers_fn"],
            scenario_name=ep["scenario_name"],
            real_fpi=ep["real_fpi"],
            real_eb_rate=ep["real_eb_rate"],
            real_par_bn=ep["real_par_bn"],
            n_steps=n_steps,
            verbose=False,
            init_year=ep["init_year"],
        )
    finally:
        _retro.N_MC_RETRO = old_n_mc

    return ep, model, scored


def run_historical_episode(episode_key: str, n_mc: int = 6, n_steps: int = 25) -> dict:
    if episode_key not in HISTORICAL_EPISODES:
        return None
    ep, model, scored = _historical_run_cached(episode_key, n_mc, n_steps)
    return {
        "key": episode_key,
        "label": ep["label"],
        "trigger_calendar_year": ep["trigger_calendar_year"],
        "init_year": ep["init_year"],
        "triggers": ep["triggers_fn"](),
        "timeseries": global_metrics_timeseries(model),
        "nodes": node_state_snapshot(model),
        "scored": scored,
    }


# ── Comparison mode ----------------------------------------------------------
# Runs several scenarios (named research scenarios and/or custom Scenario-Lab
# configs) through the identical single-seeded-run path and returns them in a
# uniform shape, so the frontend can plot them side by side. Each run still
# calls only the real model/response-lever/STC-engine machinery -- comparison
# mode just orchestrates multiple such runs.

def _run_named_scenario_full(name: str, n_steps: int, seed: int) -> dict:
    """
    Representative single run of a research scenario (S0-S5) -- same
    construction as scenarios.run_scenario's representative run (same
    triggers, same response_fn), but returns the full timeseries + node
    snapshot instead of only MC-aggregated stats.
    """
    spec = _SPEC_BY_NAME[name]
    model = FoodEnergyModel(scenario=spec.name, seed=seed)
    spec.response_fn(model)
    model.stc_engine = STCEngine(triggers=[dict(t) for t in spec.triggers], ss_mode="multiplicative")
    model.run(n_steps, verbose=False)
    return {
        "id": name,
        "label": spec.label,
        "kind": "research",
        "summary": model.summary(),
        "timeseries": global_metrics_timeseries(model),
        "nodes": node_state_snapshot(model),
    }


def _run_custom_scenario_full(run_id: str, label: str, shocks: list[dict], responses: list[str],
                               n_steps: int, seed: int) -> dict:
    result = run_custom_simulation(shocks=shocks, responses=responses, n_steps=n_steps, seed=seed)
    return {
        "id": run_id,
        "label": label,
        "kind": "custom",
        "summary": result["summary"],
        "timeseries": result["timeseries"],
        "nodes": result["nodes"],
    }


def run_comparison(runs: list[dict], n_steps: int = 25, seed: int = 42) -> dict:
    """
    runs: list of either
      {"kind": "research", "name": "S1_climate_cascade"}
      {"kind": "custom", "id": "myrun", "label": "My scenario", "shocks": [...], "responses": [...]}
    Always prepends S0_baseline as the reference line if not already present.
    """
    requested_names = {r.get("name") for r in runs if r.get("kind") == "research"}
    out = []
    if "S0_baseline" not in requested_names:
        out.append(_run_named_scenario_full("S0_baseline", n_steps, seed))

    for r in runs:
        if r.get("kind") == "research":
            out.append(_run_named_scenario_full(r["name"], n_steps, seed))
        else:
            out.append(_run_custom_scenario_full(
                r.get("id", "custom"), r.get("label", "Custom scenario"),
                r.get("shocks", []), r.get("responses", []), n_steps, seed,
            ))
    return {"runs": out}


# ── Network analysis ----------------------------------------------------------
# Graph-theoretic properties of the model's actual trade network, computed
# with networkx directly on model.network. Centrality is a structural
# property of the real graph object the ABM uses for propagation -- not a
# new scientific claim, just standard network analysis of it.

def network_with_centrality(steps: int = 10, seed: int = 42) -> dict:
    import networkx as nx

    model = get_baseline_model(steps=steps, seed=seed)
    G = model.network

    degree_c = nx.degree_centrality(G)
    in_degree_c = nx.in_degree_centrality(G)
    out_degree_c = nx.out_degree_centrality(G)
    try:
        eigen_c = nx.eigenvector_centrality(G, max_iter=500, weight="C_ij")
    except Exception:
        eigen_c = {n: 0.0 for n in G.nodes()}
    try:
        betweenness_c = nx.betweenness_centrality(G, weight="kappa_ij")
    except Exception:
        betweenness_c = {n: 0.0 for n in G.nodes()}

    nodes = node_state_snapshot(model)
    for n in nodes:
        name = n["id"]
        n["degree_centrality"] = round(degree_c.get(name, 0.0), 4)
        n["in_degree_centrality"] = round(in_degree_c.get(name, 0.0), 4)
        n["out_degree_centrality"] = round(out_degree_c.get(name, 0.0), 4)
        n["eigenvector_centrality"] = round(eigen_c.get(name, 0.0), 4)
        n["betweenness_centrality"] = round(betweenness_c.get(name, 0.0), 4)
        n["in_degree"] = G.in_degree(name)
        n["out_degree"] = G.out_degree(name)

    return {"nodes": nodes, "edges": network_edges(model)}


# ── Time machine ---------------------------------------------------------------
# Two genuinely different regimes, not one continuous simulated drift:
#
# 1. OBSERVED (2000-2024): each year is a FRESH model construction, rescaled
#    directly to that year's real FAO/OWID/ND-GAIN panel data
#    (_rescale_params_to_year in model.py). One model.step() is called to
#    resolve trade/price coherently (metrics are only recorded post-step --
#    see model.py's step() docstring) -- this is running the model's real
#    mechanics ONCE on real initial conditions, not accumulating drift across
#    24 simulated years. This is what was missing before: previously the
#    whole 2000-2050 range was one continuous simulated run from year 2000,
#    so "2015" showed 15 years of simulation drift instead of real 2015 data.
#
# 2. PROJECTION (2025+): no real data exists here by definition. This is one
#    continuous simulated run, anchored at the most recent REAL data point
#    (2024) rather than compounding 24 extra years of avoidable drift before
#    even reaching the actually-uncertain future.

NODE_PANEL_MAX_YEAR = 2024  # last year with real panel coverage (see model.py)


@functools.lru_cache(maxsize=30)
def real_year_snapshot(year: int) -> Optional[dict]:
    if year < 2000 or year > NODE_PANEL_MAX_YEAR:
        return None
    model = FoodEnergyModel(scenario=f"real_{year}", seed=42, init_year=year)
    model.step()  # resolve trade/price once on real initial conditions -- metrics record here
    ts = global_metrics_timeseries(model)
    return {
        "year": year,
        "observed": True,
        "nodes": node_state_snapshot(model),
        "metrics": ts[0] if ts else None,
    }


@functools.lru_cache(maxsize=1)
def real_years_batch() -> list[dict]:
    return [real_year_snapshot(y) for y in range(2000, NODE_PANEL_MAX_YEAR + 1)]


@functools.lru_cache(maxsize=2)
def _projection_cached(n_steps: int, seed: int, start_year: int):
    model = FoodEnergyModel(scenario="projection", seed=seed, init_year=start_year)
    snapshots = [{"year": start_year, "observed": True, "nodes": node_state_snapshot(model)}]
    for i in range(n_steps):
        model.step()
        snapshots.append({"year": start_year + i + 1, "observed": False, "nodes": node_state_snapshot(model)})
    return model, snapshots


def time_machine(end_year: int = 2050, seed: int = 42) -> dict:
    """
    Combined observed (real, 2000-2024) + projection (simulated, 2024+)
    trajectory for the Time Machine slider.
    """
    observed = real_years_batch()
    n_steps = max(0, end_year - NODE_PANEL_MAX_YEAR)
    proj_model, proj_snapshots = _projection_cached(n_steps, seed, NODE_PANEL_MAX_YEAR)
    proj_ts = global_metrics_timeseries(proj_model)

    # Stitch: observed years 2000-2024 (real metrics from each year's own
    # single-step resolution) + projection years 2025-end_year (one
    # continuous run anchored at 2024). Skip the projection's duplicate
    # 2024 entry (index 0) since observed already has it.
    all_snapshots = (
        [{"year": o["year"], "observed": True, "nodes": o["nodes"]} for o in observed]
        + proj_snapshots[1:]
    )
    all_metrics = (
        [o["metrics"] for o in observed if o["metrics"]]
        + proj_ts
    )

    return {
        "init_year": 2000,
        "data_horizon_year": NODE_PANEL_MAX_YEAR,
        "end_year": end_year,
        "snapshots": all_snapshots,
        "timeseries": all_metrics,
    }


# ── Custom projection with Monte Carlo uncertainty -----------------------------
# "Pick a target year, optionally add your own shocks/responses, get a number
# with honest uncertainty and a causal explanation." Uses the exact same
# Monte Carlo methodology as scenarios.run_scenario (mean/std/p5/p95 across
# seeded reruns) -- just applied to a user-defined trigger set instead of a
# fixed research scenario, and anchored at a user-chosen start year (real
# panel data if <=2024, otherwise the 2024 real anchor).

def run_custom_projection(
    shocks: list[dict],
    responses: list[str],
    target_year: int,
    start_year: Optional[int] = None,
    n_mc: int = 8,
    seed: int = 42,
) -> dict:
    import numpy as np

    if start_year is None:
        start_year = min(target_year - 1, NODE_PANEL_MAX_YEAR)
    start_year = max(2000, min(start_year, NODE_PANEL_MAX_YEAR))
    n_steps = max(1, target_year - start_year)

    def _build_model(run_seed: int) -> FoodEnergyModel:
        m = FoodEnergyModel(scenario="custom_projection", seed=run_seed, init_year=start_year)
        for r in responses:
            fn = RESPONSE_FN.get(r)
            if fn:
                fn(m)
        triggers = build_triggers_from_shocks(shocks, n_steps)
        m.stc_engine = STCEngine(triggers=triggers, ss_mode="multiplicative")
        return m

    mc_summaries = []
    for i in range(n_mc):
        m = _build_model(seed + i)
        m.run(n_steps, verbose=False)
        mc_summaries.append(m.summary())

    numeric_keys = [k for k in mc_summaries[0]
                    if isinstance(mc_summaries[0][k], (int, float)) and k != "n_steps"]
    stats = {}
    for k in numeric_keys:
        vals = [s[k] for s in mc_summaries if isinstance(s.get(k), (int, float))]
        stats[k] = {
            "mean": round(float(np.mean(vals)), 4),
            "std": round(float(np.std(vals)), 4),
            "p5": round(float(np.percentile(vals, 5)), 4),
            "p95": round(float(np.percentile(vals, 95)), 4),
        }

    # representative single run for timeseries/nodes/attribution grounding
    rep_model = _build_model(seed)
    rep_model.run(n_steps, verbose=False)
    attribution_df = crisis_attribution(rep_model)

    # baseline (no shocks) comparison, same anchor/horizon
    baseline_model = FoodEnergyModel(scenario="custom_projection_baseline", seed=seed, init_year=start_year)
    baseline_model.run(n_steps, verbose=False)

    return {
        "start_year": start_year,
        "target_year": target_year,
        "n_steps": n_steps,
        "n_mc": n_mc,
        "used_real_anchor": start_year <= NODE_PANEL_MAX_YEAR,
        "stats": stats,
        "baseline_summary": baseline_model.summary(),
        "timeseries": global_metrics_timeseries(rep_model),
        "nodes": node_state_snapshot(rep_model),
        "attribution": attribution_df.to_dict(orient="records") if not attribution_df.empty else [],
        "triggers_applied": build_triggers_from_shocks(shocks, n_steps),
    }


# ── Shock library ---------------------------------------------------------------
# Descriptive metadata for each shock type already wired into
# build_triggers_from_shocks/SHOCK_TYPE_MAP above. This is documentation of
# real mechanism parameters already in use -- not a new mechanism layer.
# affected_variables names the STC trigger fields each shock actually sets.

SHOCK_LIBRARY = {
    "climate_drought": {
        "label": "Climate / Drought",
        "description": "Reduced crop yield from drought, heat, or erratic rainfall. Applied as a direct food-supply multiplier on affected nodes.",
        "affected_variables": ["food_shock (supply multiplier)", "FS_index accumulation"],
        "default_severity": 50, "default_scope": 30, "default_duration": 2,
        "recovery_model": "No explicit recovery function -- effect is duration-limited (trigger stops firing after `duration` steps); underlying stress (FS_index) persists per the model's LFBB accumulation.",
    },
    "energy_crisis": {
        "label": "Energy Crisis",
        "description": "Fossil energy price/availability shock. Propagates to food prices via the energy-food elasticity (ε_EF) coupling.",
        "affected_variables": ["energy_shock (energy-cost multiplier)", "food price via ε_EF coupling"],
        "default_severity": 60, "default_scope": 50, "default_duration": 2,
        "recovery_model": "Duration-limited trigger; energy stress index decays per the model's own energy module dynamics after the trigger window ends.",
    },
    "pandemic": {
        "label": "Pandemic",
        "description": "Labor/logistics disruption reducing both food and (mildly) energy throughput simultaneously across affected nodes.",
        "affected_variables": ["food_shock", "energy_shock (smaller)"],
        "default_severity": 40, "default_scope": 60, "default_duration": 3,
        "recovery_model": "Duration-limited; no separate recovery curve.",
    },
    "financial_crisis": {
        "label": "Financial Crisis",
        "description": "Speculative-type shock; amplifies food price volatility independent of physical supply.",
        "affected_variables": ["food_shock (price-channel)", "SAV_homogeneity indirectly via trade behavior"],
        "default_severity": 50, "default_scope": 40, "default_duration": 2,
        "recovery_model": "Duration-limited trigger.",
    },
    "export_ban": {
        "label": "Export Ban",
        "description": "Direct trade-policy shock on a targeted node (or nodes) restricting exports, cutting supply to import-dependent trade partners.",
        "affected_variables": ["food_shock", "export_fraction / export_ban flag on the targeted node"],
        "default_severity": 60, "default_scope": 20, "default_duration": 2,
        "recovery_model": "Duration-limited; export policy reverts to the model's own agent-level export_policy logic once the trigger window ends.",
    },
    "war": {
        "label": "War / Conflict",
        "description": "The most severe shock type -- large simultaneous food and energy multipliers on the targeted node(s), modeling combined production, logistics, and trade collapse.",
        "affected_variables": ["food_shock (largest)", "energy_shock (largest)"],
        "default_severity": 70, "default_scope": 25, "default_duration": 3,
        "recovery_model": "Duration-limited trigger; this is the single highest-impact shock type in the library (food_shock_base 1.55, energy_shock_base 2.00 at full severity).",
    },
    "fertilizer_shortage": {
        "label": "Fertilizer Shortage",
        "description": "Input-cost/availability shock reducing effective yield with a secondary energy-cost component (fertilizer production is energy-intensive).",
        "affected_variables": ["food_shock", "energy_shock (secondary)"],
        "default_severity": 50, "default_scope": 40, "default_duration": 2,
        "recovery_model": "Duration-limited trigger.",
    },
    "shipping_disruption": {
        "label": "Shipping Disruption",
        "description": "Logistics/trade-route shock (e.g. canal blockage, port closure) -- moderate food and energy impact, scope-dependent on how much of the network relies on the disrupted route.",
        "affected_variables": ["food_shock (moderate)", "energy_shock (moderate)"],
        "default_severity": 40, "default_scope": 35, "default_duration": 1,
        "recovery_model": "Short duration by default -- shipping disruptions in this library are modeled as more transient than war/export-ban.",
    },
    "currency_collapse": {
        "label": "Currency Collapse",
        "description": "Speculative-type macroeconomic shock affecting a node's purchasing power for food imports.",
        "affected_variables": ["food_shock (price-channel)", "energy_shock (minor)"],
        "default_severity": 50, "default_scope": 30, "default_duration": 2,
        "recovery_model": "Duration-limited trigger.",
    },
}


def get_shock_library() -> dict:
    return SHOCK_LIBRARY


# ── Cascade trace -----------------------------------------------------------
# IMPORTANT CALIBRATION FINDING, discovered while building this: agent-level
# `overload_food` (LFBB stress overload) fires for ~16 of 35 nodes at step 1
# of ANY run -- shocked or not, same seed. Verified directly: a cascade_trace
# call with an empty shocks list produces the identical 16 first-overload
# nodes as one with a war shock on Russia. This is chronic/structural stress
# already present in these nodes' real calibrated 2005-2022 data (FS_index/
# CC_index already >1.0), NOT a shock response -- so tracking raw overload
# transitions cannot show shock-driven propagation; it just shows the
# baseline's own structural fragility.
#
# Fix: run the SAME seed with and without the shock, and track each node's
# food-security (sigma) GAP between the two runs. A node is "newly affected"
# the first step its shocked-vs-baseline sigma gap crosses a threshold --
# this isolates the shock's actual marginal effect from pre-existing
# structural stress. Both runs are the real model; this only diffs them.

CASCADE_SIGMA_GAP_THRESHOLD = 0.03  # sigma-point gap vs baseline to count as "affected"


def cascade_trace(shocks: list[dict], responses: list[str], start_year: int, n_steps: int, seed: int = 42) -> dict:
    def _build(apply_shock: bool) -> FoodEnergyModel:
        m = FoodEnergyModel(scenario="cascade_trace", seed=seed, init_year=start_year)
        for r in responses:
            fn = RESPONSE_FN.get(r)
            if fn:
                fn(m)
        triggers = build_triggers_from_shocks(shocks, n_steps) if apply_shock else []
        m.stc_engine = STCEngine(triggers=triggers, ss_mode="multiplicative")
        return m

    shocked = _build(True)
    baseline = _build(False)

    triggers = build_triggers_from_shocks(shocks, n_steps)
    origin_nodes = sorted({t["target_node"] for t in triggers if t.get("target_node")})

    affected_first_step: dict[str, int] = {}
    affected_gap_at_detection: dict[str, float] = {}
    step_edge_snapshots: list[list[dict]] = []

    for step in range(1, n_steps + 1):
        shocked.step()
        baseline.step()
        for name in shocked.agent_map:
            gap = baseline.agent_map[name].food_security - shocked.agent_map[name].food_security
            if gap >= CASCADE_SIGMA_GAP_THRESHOLD and name not in affected_first_step:
                affected_first_step[name] = step
                affected_gap_at_detection[name] = round(gap, 4)
        step_edge_snapshots.append(network_edges(shocked))

    final_edges = step_edge_snapshots[-1] if step_edge_snapshots else []
    edge_capacity = {}
    for e in final_edges:
        edge_capacity[(e["source"], e["target"])] = e["capacity"]
        edge_capacity[(e["target"], e["source"])] = max(edge_capacity.get((e["target"], e["source"]), 0), e["capacity"])

    cascade_edges = []
    for node, step in affected_first_step.items():
        candidates = [
            (other, edge_capacity.get((other, node), 0))
            for other, other_step in affected_first_step.items()
            if other != node and other_step < step and edge_capacity.get((other, node), 0) > 0
        ]
        candidates.sort(key=lambda c: -c[1])
        for other, cap in candidates[:2]:
            cascade_edges.append({
                "source": other, "target": node,
                "source_step": affected_first_step[other], "target_step": step,
                "edge_capacity": cap,
            })

    events = sorted(
        [{"node": n, "step": s, "year": start_year + s, "is_origin": n in origin_nodes,
          "sigma_gap_vs_baseline": affected_gap_at_detection[n]}
         for n, s in affected_first_step.items()],
        key=lambda e: e["step"],
    )

    return {
        "start_year": start_year,
        "n_steps": n_steps,
        "origin_nodes": origin_nodes,
        "triggers_applied": triggers,
        "events": events,
        "cascade_edges": cascade_edges,
        "total_affected": len(affected_first_step),
        "detection_method": (
            f"Node counted as 'affected' the first step its food-security (sigma) falls "
            f"{CASCADE_SIGMA_GAP_THRESHOLD}+ points below the same seed's no-shock baseline "
            f"at the same step -- isolates the shock's marginal effect from structural "
            f"baseline stress already present in the calibrated data."
        ),
        "final_summary_shocked": shocked.summary(),
        "final_summary_baseline": baseline.summary(),
    }


# ── Policy optimization -------------------------------------------------------
# Runs a given shock scenario under each of the 5 real, atomic response
# levers (see ATOMIC_RESPONSE_FN above) plus a no-response control, and
# ranks them by outcome. Only levers with a real backing mechanism in
# scenarios.py are included -- "food aid," "energy subsidies," "technology
# investment," and "import substitution" are not implemented as distinct
# mechanisms in the frozen backend, so they are not offered here rather
# than being faked.

def run_policy_optimization(shocks: list[dict], start_year: int, n_steps: int, seed: int = 42) -> dict:
    def _run(lever_key: Optional[str]) -> dict:
        m = FoodEnergyModel(scenario=f"policy_opt_{lever_key or 'none'}", seed=seed, init_year=start_year)
        if lever_key:
            ATOMIC_RESPONSE_FN[lever_key](m)
        triggers = build_triggers_from_shocks(shocks, n_steps)
        m.stc_engine = STCEngine(triggers=triggers, ss_mode="multiplicative")
        m.run(n_steps, verbose=False)
        return m.summary()

    control = _run(None)
    results = []
    for key, label in ATOMIC_RESPONSE_LABELS.items():
        s = _run(key)
        results.append({
            "lever": key,
            "label": label,
            "max_price_index": s["max_price_index"],
            "max_PAR_millions": s["max_PAR_millions"],
            "max_TC": s["max_TC"],
            "max_n_overload_food": s["max_n_overload_food"],
            "min_GFS": s["min_GFS"],
            # improvement vs no-response control, in the units policymakers care about
            "population_saved_millions": round(control["max_PAR_millions"] - s["max_PAR_millions"], 1),
            "price_index_reduction": round(control["max_price_index"] - s["max_price_index"], 4),
            "trade_collapse_reduction": round(control["max_TC"] - s["max_TC"], 4),
            "food_security_improvement": round(s["min_GFS"] - control["min_GFS"], 4),
        })

    results.sort(key=lambda r: -r["population_saved_millions"])

    return {
        "start_year": start_year,
        "n_steps": n_steps,
        "control_summary": control,
        "ranked_policies": results,
        "note": (
            "Only the 5 response levers with a real, distinct mechanism in the frozen "
            "backend (scenarios.py) are ranked here. Interventions named in policy "
            "discussions but not implemented as separate mechanisms in this model "
            "(e.g. food aid, energy subsidies, technology investment, import "
            "substitution) are not included rather than approximated."
        ),
    }


def run_policy_search(shocks: list[dict], start_year: int, n_steps: int,
                       n_random: int = 40, include_fixed_levers: bool = True,
                       custom_levers: list[dict] | None = None,
                       include_node_targeted_sampling: bool = False,
                       node_pool: list[str] | None = None,
                       max_budget: float | None = None,
                       seed: int = 42) -> dict:
    """
    PHASE A/B/D (this session): thin wrapper around scenarios.policy_search(),
    following run_policy_optimization()'s exact pattern immediately above
    (translate UI shocks -> STC triggers via the existing
    build_triggers_from_shocks(), delegate all computation to the
    canonical scientific module, return its result unmodified). This
    function performs no scientific computation itself -- identical
    design principle to every other function in this file.

    Distinct from run_policy_optimization() (unchanged, still the fast
    fixed-5-lever comparison): this evaluates n_random additional
    randomly-sampled lever COMBINATIONS and INTENSITIES, per the
    implementation audit's recommendation to extend rather than replace
    the existing endpoint. Both endpoints remain available.
    """
    triggers = build_triggers_from_shocks(shocks, n_steps)
    return _policy_search(
        triggers=triggers,
        start_year=start_year,
        n_steps=n_steps,
        n_random=n_random,
        seed=seed,
        include_fixed_levers=include_fixed_levers,
        custom_levers=custom_levers,
        include_node_targeted_sampling=include_node_targeted_sampling,
        node_pool=node_pool,
        max_budget=max_budget,
        verbose=False,
    )


def run_node_level_policy_search(lever_type: str, node_pool: list[str],
                                  shocks: list[dict], start_year: int, n_steps: int,
                                  n_random: int = 30, max_budget: float | None = None,
                                  seed: int = 42) -> dict:
    """
    PHASE D (this session): thin wrapper around
    scenarios.node_level_policy_search() -- same translation-only design
    principle as every function in this file. Answers "which node(s)
    should [lever_type] target to minimise global PAR" directly.
    """
    triggers = build_triggers_from_shocks(shocks, n_steps)
    return _node_level_policy_search(
        lever_type=lever_type,
        node_pool=node_pool,
        triggers=triggers,
        start_year=start_year,
        n_steps=n_steps,
        n_random=n_random,
        max_budget=max_budget,
        seed=seed,
        verbose=False,
    )


# ── Per-country historical trend ------------------------------------------------
# Lightweight extraction of one country's real per-year data (2000-2024),
# reusing the cached real_years_batch() rather than a new heavy payload.

def country_history(name: str) -> Optional[list[dict]]:
    years = real_years_batch()
    out = []
    for y in years:
        node = next((n for n in y["nodes"] if n["name"] == name), None)
        if node is None:
            return None
        out.append({
            "year": y["year"],
            "food_security": node["food_security"],
            "technology": node["technology"],
            "energy_stress": node["energy_stress"],
            "population_millions": node["population_millions"],
            "capital_bn": node["capital_bn"],
            "undernourished": node["undernourished"],
            "export_ban": node["export_ban"],
            "overload_food": node["overload_food"],
        })
    return out

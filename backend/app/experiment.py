"""
experiment.py
--------------
The canonical backend entry point. An Experiment is: a world-state anchor
(real calibrated year), an optional shock specification (custom, or one of
the real historical trigger sets), optional interventions, and an
uncertainty configuration. Running it always produces the same
ExperimentResult shape -- timeseries, per-step snapshots, final node
state, a cascade trace, a contribution decomposition, uncertainty stats
(when Monte Carlo was requested), and a grounded explanation -- regardless
of which of the three modes (historical / counterfactual / projection)
produced it. Every existing bridge function this calls is still the real,
unmodified ABM; this module only orchestrates and shapes the output.
"""
from __future__ import annotations

from typing import Optional
import numpy as np

from . import model_bridge as mb
from . import experiment_store as store
from .ai_providers import get_active_provider, MockProvider

CASCADE_SIGMA_GAP_THRESHOLD = 0.03


def _resolve_triggers(spec: dict, n_steps: int) -> tuple[list[dict], int, dict]:
    """
    Returns (triggers, effective_anchor_year, episode_meta).
    If spec['known_episode'] names one of the real historical episodes,
    that episode's own real trigger set and init_year take precedence over
    freeform shocks (you get the real 2008 crisis triggers, not an
    approximation of them).
    """
    episode_key = spec.get("known_episode")
    if episode_key:
        if episode_key in mb.HISTORICAL_EPISODES:
            ep = mb.HISTORICAL_EPISODES[episode_key]
            return ep["triggers_fn"](), ep["init_year"], {
                "kind": "scored_historical", "key": episode_key, "label": ep["label"],
            }
        if episode_key in mb.DESCRIPTIVE_EPISODES:
            ep = mb.DESCRIPTIVE_EPISODES[episode_key]
            return ep["triggers_fn"](), ep["init_year"], {
                "kind": "descriptive_historical", "key": episode_key, "label": ep["label"], "note": ep["note"],
            }
    shocks = spec.get("shocks", [])
    return mb.build_triggers_from_shocks(shocks, n_steps), spec["anchor_year"], {}


def _run_single(anchor_year: int, triggers: list[dict], responses: list[str], n_steps: int, seed: int):
    """One deterministic run, capturing full per-step snapshots for scrubbing."""
    from model import FoodEnergyModel   # already on sys.path via model_bridge
    from stc_engine import STCEngine

    model = FoodEnergyModel(scenario="experiment", seed=seed, init_year=anchor_year)
    for r in responses:
        fn = mb.RESPONSE_FN.get(r)
        if fn:
            fn(model)
    model.stc_engine = STCEngine(triggers=[dict(t) for t in triggers], ss_mode="multiplicative")

    snapshots = [{"step": 0, "year": anchor_year, "nodes": mb.node_state_snapshot(model)}]
    for i in range(n_steps):
        model.step()
        snapshots.append({"step": i + 1, "year": anchor_year + i + 1, "nodes": mb.node_state_snapshot(model)})
    return model, snapshots


def _cascade_from_pair(shocked_model, baseline_model, anchor_year: int, n_steps: int, origin_nodes: list[str]):
    """
    Re-derives the cascade by re-running both models' recorded trajectory --
    cheaper alternative: we already have per-step snapshots from _run_single,
    but computing the sigma gap needs BOTH models stepped in lockstep, so
    this is called with two freshly-run models sharing the same seed/config
    apart from the shock, mirroring model_bridge.cascade_trace's validated
    methodology (a no-shock control must show zero affected nodes).
    """
    affected_first_step: dict[str, int] = {}
    affected_gap: dict[str, float] = {}
    for step in range(1, n_steps + 1):
        for name in shocked_model.agent_map:
            s_sigma = shocked_model.agent_map[name].food_security
            b_sigma = baseline_model.agent_map[name].food_security
            gap = b_sigma - s_sigma
            if gap >= CASCADE_SIGMA_GAP_THRESHOLD and name not in affected_first_step:
                affected_first_step[name] = step
                affected_gap[name] = round(gap, 4)
    events = sorted(
        [{"node": n, "step": s, "year": anchor_year + s, "is_origin": n in origin_nodes,
          "sigma_gap_vs_baseline": affected_gap[n]} for n, s in affected_first_step.items()],
        key=lambda e: e["step"],
    )
    return {"events": events, "total_affected": len(affected_first_step)}


def _mc_stats(anchor_year: int, triggers: list[dict], responses: list[str], n_steps: int, seed: int, n_mc: int):
    from model import FoodEnergyModel
    from stc_engine import STCEngine

    summaries = []
    for i in range(n_mc):
        m = FoodEnergyModel(scenario="experiment_mc", seed=seed + i, init_year=anchor_year)
        for r in responses:
            fn = mb.RESPONSE_FN.get(r)
            if fn:
                fn(m)
        m.stc_engine = STCEngine(triggers=[dict(t) for t in triggers], ss_mode="multiplicative")
        m.run(n_steps, verbose=False)
        summaries.append(m.summary())

    keys = [k for k in summaries[0] if isinstance(summaries[0][k], (int, float)) and k != "n_steps"]
    stats = {}
    for k in keys:
        vals = [s[k] for s in summaries if isinstance(s.get(k), (int, float))]
        stats[k] = {
            "mean": round(float(np.mean(vals)), 4), "std": round(float(np.std(vals)), 4),
            "p5": round(float(np.percentile(vals, 5)), 4), "p95": round(float(np.percentile(vals, 95)), 4),
        }
    return stats


def _explain(spec: dict, result: dict) -> tuple[str, str]:
    grounding_data = {
        "mode": spec["mode"],
        "anchor_year": result["anchor_year"],
        "target_year": result["target_year"],
        "n_steps": result["n_steps"],
        "has_shock": len(result["triggers_applied"]) > 0,
        "shock_count": len(result["triggers_applied"]),
        "total_affected": result["cascade"]["total_affected"] if result.get("cascade") else 0,
        "top_affected": [e["node"] for e in result["cascade"]["events"][:5]] if result.get("cascade") else [],
        "final_price_index": result["summary"].get("max_price_index"),
        "baseline_price_index": result["baseline_summary"].get("max_price_index"),
        "final_par_bn": (result["summary"].get("max_PAR_millions") or 0) / 1000,
        "baseline_par_bn": (result["baseline_summary"].get("max_PAR_millions") or 0) / 1000,
        "has_uncertainty": result.get("uncertainty") is not None,
        "uncertainty_price": result.get("uncertainty", {}).get("max_price_index") if result.get("uncertainty") else None,
        "episode_meta": result.get("episode_meta", {}),
    }
    provider = get_active_provider()
    try:
        text = provider.explain("Explain this experiment's outcome.", {"intent": "experiment", "data": grounding_data})
        return text, provider.name
    except Exception:
        text = MockProvider().explain("Explain this experiment's outcome.", {"intent": "experiment", "data": grounding_data})
        return text, "mock"


def create_experiment(spec: dict) -> dict:
    """
    spec (already validated by the ExperimentCreateRequest schema, passed
    in as a plain dict): mode, anchor_year, target_year, known_episode?,
    shocks[], responses[], n_mc, seed, explain, evaluate_policies,
    target_country?, parent_id?, label?, annotation?
    """
    n_steps_requested = max(1, spec["target_year"] - spec["anchor_year"])
    triggers, effective_anchor, episode_meta = _resolve_triggers(spec, n_steps_requested)
    anchor_year = effective_anchor

    target_year = spec["target_year"]
    if episode_meta and target_year <= anchor_year:
        # A known episode moved the anchor to its own real init_year, which
        # can land after the user's original target_year (e.g. anchor_year
        # requested=2000 but the 2022 episode's real init_year is 2018).
        # Extend the horizon rather than silently running ~0 steps and
        # producing a near-empty result with none of the episode's own
        # triggers (which fire at specific step offsets) ever reached.
        target_year = anchor_year + max(n_steps_requested, 25)

    n_steps = max(1, target_year - anchor_year)
    seed = spec.get("seed", 42)
    responses = spec.get("responses", [])

    shocked_model, snapshots = _run_single(anchor_year, triggers, responses, n_steps, seed)
    baseline_model, _ = _run_single(anchor_year, [], [], n_steps, seed)

    origin_nodes = sorted({t["target_node"] for t in triggers if t.get("target_node")})
    cascade = _cascade_from_pair(shocked_model, baseline_model, anchor_year, n_steps, origin_nodes) if triggers else None

    attribution_df = mb.crisis_attribution(shocked_model)
    attribution = attribution_df.to_dict(orient="records") if not attribution_df.empty else []

    uncertainty = None
    n_mc = spec.get("n_mc", 1)
    if n_mc and n_mc > 1:
        uncertainty = _mc_stats(anchor_year, triggers, responses, n_steps, seed, n_mc)

    policy_rankings = None
    if spec.get("evaluate_policies") and triggers:
        shocks_for_policy = spec.get("shocks", [])
        policy_rankings = mb.run_policy_optimization(shocks_for_policy, anchor_year, n_steps, seed)

    result = {
        "anchor_year": anchor_year,
        "target_year": target_year,
        "n_steps": n_steps,
        "summary": shocked_model.summary(),
        "baseline_summary": baseline_model.summary(),
        "timeseries": mb.global_metrics_timeseries(shocked_model),
        "baseline_timeseries": mb.global_metrics_timeseries(baseline_model),
        "snapshots": snapshots,
        "nodes": mb.node_state_snapshot(shocked_model),
        "triggers_applied": triggers,
        "origin_nodes": origin_nodes,
        "cascade": cascade,
        "attribution": attribution,
        "uncertainty": uncertainty,
        "policy_rankings": policy_rankings,
        "episode_meta": episode_meta,
    }

    explanation, provider_name = (None, None)
    if spec.get("explain", True):
        explanation, provider_name = _explain(spec, result)
    result["explanation"] = explanation
    result["explanation_provider"] = provider_name

    metadata = {
        "id": store.new_id(),
        "label": spec.get("label") or _default_label(spec, episode_meta),
        "mode": spec["mode"],
        "parent_id": spec.get("parent_id"),
        "created_at": store.now_iso(),
        "annotation": spec.get("annotation"),
        "target_country": spec.get("target_country"),
    }

    experiment = {
        "metadata": metadata,
        "spec": spec,
        "result": result,
    }
    store.save_experiment(experiment)
    return experiment


def _default_label(spec: dict, episode_meta: dict) -> str:
    if episode_meta.get("label"):
        return episode_meta["label"]
    if spec["mode"] == "historical":
        return f"{spec['anchor_year']} world state"
    if spec["mode"] == "counterfactual":
        shock_types = {s.get("shock_type") for s in spec.get("shocks", [])}
        return f"What if {', '.join(shock_types) or 'a shock'} in {spec['anchor_year']}?"
    return f"Projection to {spec['target_year']}"


def branch_experiment(experiment_id: str, overrides: dict) -> Optional[dict]:
    parent = store.load_experiment(experiment_id)
    if parent is None:
        return None
    new_spec = dict(parent["spec"])
    new_spec.update(overrides)
    new_spec["parent_id"] = experiment_id
    new_spec["label"] = overrides.get("label") or f"{parent['metadata']['label']} (branch)"
    return create_experiment(new_spec)

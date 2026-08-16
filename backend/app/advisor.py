"""
advisor.py
----------
Routes a natural-language policy question to a real backend simulation
call, then hands the (already-computed) numbers to an AIProvider to
explain. The parsing here is intentionally simple keyword/regex matching --
it decides WHICH real simulation to run, it does not compute any science
itself. If no intent matches, the advisor says so rather than guessing.
"""
from __future__ import annotations

import re
from . import model_bridge as mb
from .ai_providers import get_active_provider


def _find_country(question: str) -> str | None:
    q = question.lower()
    countries = mb.list_countries()
    matches = [c["name"] for c in countries if c["name"].lower() in q]
    if not matches:
        return None
    # longest match wins (avoids "Central Africa" matching inside "Central African-other" etc.)
    return max(matches, key=len)


def _find_percent(question: str) -> float | None:
    m = re.search(r"(\d{1,3})\s*%", question)
    if m:
        return float(m.group(1))
    if re.search(r"\bdoubl", question, re.I):
        return 80.0
    if re.search(r"\btripl", question, re.I):
        return 95.0
    return None


def answer_question(question: str) -> dict:
    q = question.lower()
    country = _find_country(question)
    pct = _find_percent(question)

    # ── Intent: who should get aid first ────────────────────────────────
    if any(kw in q for kw in ["aid first", "receive aid", "prioritize aid", "which countries should", "most at risk", "most at-risk"]):
        model = mb.get_baseline_model(steps=10)
        nodes = sorted(mb.node_state_snapshot(model), key=lambda n: n["food_security"])
        grounding = {
            "intent": "ranking_aid",
            "data": {
                "total_nodes": len(nodes),
                "ranked": [{"name": n["name"], "food_security": n["food_security"]} for n in nodes],
            },
        }
        return _finalize(question, grounding)

    # ── Intent: best policy intervention ────────────────────────────────
    if any(kw in q for kw in ["best intervention", "best policy", "best response", "minimizes", "minimize hunger", "which intervention"]):
        candidates = [
            ("S3_reserve_mandate", "Strategic reserves"),
            ("S4_trade_diversification", "Trade diversification"),
            ("S5_transformational", "Transformational (full response)"),
        ]
        ranked = []
        for name, label in candidates:
            r = mb._run_named_scenario_full(name, n_steps=20, seed=42)
            ranked.append({
                "label": label,
                "max_par_bn": r["summary"]["max_PAR_millions"] / 1000,
                "max_price_index": r["summary"]["max_price_index"],
            })
        ranked.sort(key=lambda r: r["max_par_bn"])
        grounding = {"intent": "policy_comparison", "data": {"ranked": ranked}}
        return _finalize(question, grounding)

    # ── Intent: country-specific production/climate shock ──────────────
    if country and any(kw in q for kw in ["production", "wheat", "yield", "harvest", "lose", "loses", "losing", "crop", "drought"]):
        severity = pct if pct is not None else 40.0
        n_steps = 15
        result = mb.run_custom_simulation(
            shocks=[{"shock_type": "climate_drought", "start_step": 3, "duration": 1,
                     "severity": severity, "scope": 15, "target_node": country}],
            responses=[], n_steps=n_steps, seed=42,
        )
        baseline = mb.run_baseline_comparison(n_steps=n_steps, seed=42)
        country_node = next((n for n in result["nodes"] if n["name"] == country), None)
        grounding = {
            "intent": "country_shock",
            "data": {
                "country": country,
                "severity": severity,
                "start_step": 3,
                "n_steps": n_steps,
                "country_food_security": country_node["food_security"] if country_node else None,
                "country_status": ("crisis" if country_node and country_node["food_security"] < 0.8
                                    else "elevated" if country_node and country_node["food_security"] < 1.0
                                    else "secure") if country_node else "unknown",
                "baseline_par_bn": baseline["summary"]["max_PAR_millions"] / 1000,
                "scenario_par_bn": result["summary"]["max_PAR_millions"] / 1000,
                "baseline_price_index": baseline["summary"]["max_price_index"],
                "scenario_price_index": result["summary"]["max_price_index"],
            },
        }
        return _finalize(question, grounding)

    # ── Intent: global energy shock ─────────────────────────────────────
    if any(kw in q for kw in ["oil", "energy price", "energy crisis", "fuel"]):
        severity = pct if pct is not None else 70.0
        n_steps = 15
        result = mb.run_custom_simulation(
            shocks=[{"shock_type": "energy_crisis", "start_step": 3, "duration": 2,
                     "severity": severity, "scope": 100, "target_node": None}],
            responses=[], n_steps=n_steps, seed=42,
        )
        baseline = mb.run_baseline_comparison(n_steps=n_steps, seed=42)
        grounding = {
            "intent": "global_energy_shock",
            "data": {
                "severity": severity,
                "n_steps": n_steps,
                "baseline_par_bn": baseline["summary"]["max_PAR_millions"] / 1000,
                "scenario_par_bn": result["summary"]["max_PAR_millions"] / 1000,
                "baseline_price_index": baseline["summary"]["max_price_index"],
                "scenario_price_index": result["summary"]["max_price_index"],
                "baseline_tc": baseline["summary"]["max_TC"],
                "scenario_tc": result["summary"]["max_TC"],
            },
        }
        return _finalize(question, grounding)

    # ── Fallback: baseline global summary (covers "how many people become
    #    food insecure" and any unmatched question with real numbers, not a
    #    "no idea" response) ─────────────────────────────────────────────
    if any(kw in q for kw in ["food insecure", "hungry", "undernourish", "at risk", "how many people"]):
        model = mb.get_baseline_model(steps=10)
        ts = mb.global_metrics_timeseries(model)
        cur = ts[-1]
        grounding = {
            "intent": "baseline_query",
            "data": {
                "n_steps": 10,
                "gfs": cur["GFS"],
                "par_bn": cur["PAR_millions"] / 1000,
                "price_index": cur["price_index"],
                "n_overload": cur["n_overload_food"],
            },
        }
        return _finalize(question, grounding)

    return _finalize(question, {"intent": "unmatched", "data": {}})


def _finalize(question: str, grounding: dict) -> dict:
    provider = get_active_provider()
    try:
        answer = provider.explain(question, grounding)
    except Exception as e:  # noqa: BLE001 -- real-provider network/auth errors fall back to Mock
        from .ai_providers import MockProvider
        answer = MockProvider().explain(question, grounding)
        return {"answer": answer, "provider": "mock", "provider_error": str(e), "grounding": grounding}
    return {"answer": answer, "provider": provider.name, "grounding": grounding}

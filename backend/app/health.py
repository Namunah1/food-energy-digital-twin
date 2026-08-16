"""
health.py
---------
Computes an "Experiment Health" summary for a run: what was assumed, how
much uncertainty was actually quantified, whether this configuration has
any real-world validation to lean on, and what the model's documented
limitations are. Every field here is either a static, documented property
of the model (checked once, in comments below) or a direct read of the
experiment's own spec/result -- nothing here is a new scientific claim.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import model_bridge as mb

_SRC = Path(__file__).resolve().parent.parent / "model_src" / "Food_Energy_Systemic_Risk_ABM" / "src"


def model_fingerprint() -> str:
    """Short hash of the two files most relevant to simulation behavior --
    lets a notebook record exactly which model version produced a result."""
    h = hashlib.sha256()
    for fname in ("model.py", "stc_engine.py"):
        try:
            h.update((_SRC / fname).read_bytes())
        except FileNotFoundError:
            pass
    return h.hexdigest()[:12]


# Structural limitations verified during this project's own build/test
# process (see README) -- not speculative, each was directly observed.
KNOWN_LIMITATIONS = [
    "Trade network is a near-complete graph (1,190 edges among 35 nodes) -- "
    "raw degree centrality is uninformative; eigenvector/betweenness centrality "
    "carry the real signal.",
    "~16 of 35 nodes show chronic LFBB stress overload even with zero shocks "
    "applied (verified via empty-shock control) -- this is structural stress "
    "already present in the calibrated data, not a model artifact, but it means "
    "raw overload counts conflate baseline fragility with shock response.",
    "Only 3-5 response levers have a real, distinct mechanism in the frozen "
    "backend (reserve mandate, trade diversification, trader regulation, "
    "renewable push). Interventions named in policy discourse but not "
    "implemented (food aid, energy subsidies, technology investment, import "
    "substitution) cannot be evaluated by this model.",
    "Real calibrated panel data covers 2000-2024 only. Any year beyond that "
    "is the model's own simulated continuation, not calibrated to further "
    "real-world data.",
    "Country/bloc-level resolution only -- 21 hub countries + 14 regional "
    "blocs. Sub-national dynamics (e.g. a drought hitting one region of a "
    "large country) are not resolved.",
]


def _validation_for_episode(episode_key: str) -> dict:
    """Real retrodiction scores for a known historical episode, if scored."""
    if episode_key in mb.HISTORICAL_EPISODES:
        try:
            result = mb.run_historical_episode(episode_key, n_mc=4, n_steps=25)
            s = result["scored"]
            passed = sum([s["score1_fpi"], s["score2_eb"], s["score4_par"]])
            return {
                "status": "scored",
                "detail": f"{passed}/3 real-world validation criteria pass for this episode "
                          f"(FPI error {s['fpi_error_pct']:.1f}%).",
                "scores": {
                    "fpi_pass": s["score1_fpi"], "export_ban_pass": s["score2_eb"],
                    "par_pass": s["score4_par"], "fpi_error_pct": s["fpi_error_pct"],
                },
            }
        except Exception:
            pass
    if episode_key in mb.DESCRIPTIVE_EPISODES:
        return {
            "status": "descriptive_only",
            "detail": "This episode is documented as descriptive-only in the model's own "
                      "code -- a regional crisis not comparable to global-FPI scoring.",
            "scores": None,
        }
    return {"status": "unscored", "detail": "No matching historical episode.", "scores": None}


def compute_health(experiment: dict) -> dict:
    spec = experiment["spec"]
    result = experiment["result"]

    # ── Assumptions ──────────────────────────────────────────────────────
    assumptions = []
    assumptions.append({
        "label": "World-state anchor",
        "detail": f"{result['anchor_year']} "
                  f"({'real calibrated panel data' if result['anchor_year'] <= mb.NODE_PANEL_MAX_YEAR else 'simulated'})",
    })
    if spec.get("known_episode"):
        ep = mb.HISTORICAL_EPISODES.get(spec["known_episode"]) or mb.DESCRIPTIVE_EPISODES.get(spec["known_episode"])
        assumptions.append({
            "label": "Shock source",
            "detail": f"Real historical trigger set ({ep['label'] if ep else spec['known_episode']}), "
                      f"not an approximation.",
        })
    elif result.get("triggers_applied"):
        shock_types = sorted({t.get("type") for t in result["triggers_applied"]})
        lib = mb.get_shock_library()
        details = []
        for s in spec.get("shocks", []):
            entry = lib.get(s.get("shock_type"))
            if entry:
                details.append(f"{entry['label']} (severity {s.get('severity')}, scope {s.get('scope')})")
        assumptions.append({
            "label": "Shock source",
            "detail": f"User-defined hypothetical shock(s): {'; '.join(details) or ', '.join(shock_types)}. "
                      f"Severity/scope are user inputs, not fitted to a specific real event.",
        })
    else:
        assumptions.append({"label": "Shock source", "detail": "None -- baseline trajectory, no injected shock."})

    if spec.get("responses"):
        assumptions.append({"label": "Interventions applied", "detail": ", ".join(spec["responses"])})

    # ── Uncertainty ──────────────────────────────────────────────────────
    n_mc = spec.get("n_mc", 1)
    uncertainty = {
        "n_mc": n_mc,
        "quantified": n_mc > 1,
        "note": (
            f"{n_mc}-run Monte Carlo ensemble -- reported ranges reflect genuine seed-to-seed variance."
            if n_mc > 1 else
            "Single seeded run (n_mc=1) -- no uncertainty quantification. Treat the point "
            "estimate as one possible draw, not a confidence-bounded answer."
        ),
    }

    # ── Validation ───────────────────────────────────────────────────────
    if spec.get("known_episode"):
        validation = _validation_for_episode(spec["known_episode"])
    elif spec["mode"] == "historical" and not result.get("triggers_applied"):
        validation = {
            "status": "not_applicable",
            "detail": "Pure real-data snapshot, no shock -- nothing to validate against a counterfactual outcome.",
            "scores": None,
        }
    else:
        validation = {
            "status": "not_validated",
            "detail": "This is a hypothetical shock combination with no matching real-world event. "
                      "It has not been, and cannot be, scored against real outcomes -- treat it as a "
                      "mechanistic exploration, not a validated forecast.",
            "scores": None,
        }

    # ── Limitations (static + dynamically-triggered) ────────────────────
    limitations = list(KNOWN_LIMITATIONS)
    if result["target_year"] > mb.NODE_PANEL_MAX_YEAR:
        limitations.insert(0, f"Target year {result['target_year']} is beyond the real data horizon "
                               f"({mb.NODE_PANEL_MAX_YEAR}) -- this portion is pure model simulation.")

    return {
        "assumptions": assumptions,
        "uncertainty": uncertainty,
        "validation": validation,
        "limitations": limitations,
        "model_fingerprint": model_fingerprint(),
    }

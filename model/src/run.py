"""
run.py
------
CLI entry point for the Global Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — Baseline food-system run

Usage:
  python src/run.py --scenario baseline --steps 30 --seed 42
  python src/run.py --scenario climate_shock --steps 30 --shock_step 10
  python src/run.py --scenario ukraine_trigger --steps 30 --shock_step 5

Outputs (saved to data/processed/):
  metrics_<scenario>.csv    — per-step global metrics
  nodes_<scenario>.csv      — per-node state at final step
  summary_<scenario>.json   — quick summary dict
"""

import argparse
import sys
import json
from pathlib import Path

# Add src/ to path when running as a script
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from model import FoodEnergyModel

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = _SRC.parent
_OUT  = _ROOT / "data" / "processed"
_FIG  = _ROOT / "figures"
_OUT.mkdir(parents=True, exist_ok=True)
_FIG.mkdir(parents=True, exist_ok=True)


def run_baseline(steps: int, seed: int) -> FoodEnergyModel:
    """30-step baseline run — no shocks, no STC engine."""
    model = FoodEnergyModel(scenario="baseline", seed=seed)
    print(f"\n{'='*60}")
    print(f"  BASELINE RUN  |  steps={steps}  |  seed={seed}")
    print(f"{'='*60}\n")
    model.run(steps, verbose=True)
    return model


def run_climate_shock(steps: int, seed: int, shock_step: int) -> FoodEnergyModel:
    """
    Climate shock scenario: Australian-drought-style compound event
    injected at shock_step, affecting 40% of nodes.
    """
    model = FoodEnergyModel(scenario="climate_shock", seed=seed)
    print(f"\n{'='*60}")
    print(f"  CLIMATE SHOCK  |  steps={steps}  |  shock@t={shock_step}")
    print(f"{'='*60}\n")

    for i in range(steps):
        if i == shock_step:
            model.apply_climate_shock(
                scope=0.40, severity=0.55, mode="drought", seed_node="Australia"
            )
        model.step()
        m = model.metrics._records[-1]
        if i == 0 or (i + 1) % 5 == 0 or i == shock_step:
            print(
                f"  Step {model.steps:>3} | "
                f"GFS={m['GFS']:.3f} | "
                f"U={m['U_undernourished']:.3f} | "
                f"Price={m['price_index']:.3f} | "
                f"EB={m['EB_export_ban_rate']:.2f}"
            )
    return model


def run_ukraine_trigger(steps: int, seed: int, shock_step: int) -> FoodEnergyModel:
    """
    Ukraine-2022 trigger scenario: Russia and Ukraine export edges disabled
    at shock_step, plus a price shock (proximate trigger of Russian invasion).
    """
    model = FoodEnergyModel(scenario="ukraine_trigger", seed=seed)
    print(f"\n{'='*60}")
    print(f"  UKRAINE TRIGGER  |  steps={steps}  |  trigger@t={shock_step}")
    print(f"{'='*60}\n")

    for i in range(steps):
        if i == shock_step:
            # Disable Russia + Ukraine export edges
            model.disable_trade_edges("Russia")
            model.disable_trade_edges("Ukraine")
            # Price spike (speculative surge on trigger)
            model.apply_price_shock(factor=1.45)
            # Energy stress bump (sanction effect)
            model.sanction_penalty = 0.25
        model.step()
        m = model.metrics._records[-1]
        if i == 0 or (i + 1) % 5 == 0 or i == shock_step:
            print(
                f"  Step {model.steps:>3} | "
                f"GFS={m['GFS']:.3f} | "
                f"U={m['U_undernourished']:.3f} | "
                f"Price={m['price_index']:.3f} | "
                f"EB={m['EB_export_ban_rate']:.2f}"
            )
    return model


SCENARIOS = {
    "baseline":        run_baseline,
    "climate_shock":   run_climate_shock,
    "ukraine_trigger": run_ukraine_trigger,
}


def save_outputs(model: FoodEnergyModel, out_dir: Path):
    """Save metrics CSV, node CSV, and summary JSON."""
    sc = model._scenario_name

    metrics_path = out_dir / f"metrics_{sc}.csv"
    nodes_path   = out_dir / f"nodes_{sc}.csv"
    summary_path = out_dir / f"summary_{sc}.json"

    model.metrics_dataframe().to_csv(metrics_path, index=False)
    model.node_dataframe().to_csv(nodes_path, index=False)

    summary = model.summary()
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[Output] Metrics   → {metrics_path}")
    print(f"[Output] Node snap → {nodes_path}")
    print(f"[Output] Summary   → {summary_path}")

    return metrics_path, nodes_path


def main():
    parser = argparse.ArgumentParser(
        description="Global Food-Energy Systemic Risk ABM — Phase 2"
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="baseline",
        help="Scenario to run",
    )
    parser.add_argument("--steps",      type=int, default=30, help="Number of simulation steps (years)")
    parser.add_argument("--seed",       type=int, default=42, help="Random seed")
    parser.add_argument("--shock_step", type=int, default=10, help="Step at which shock/trigger fires")
    parser.add_argument("--no_viz",     action="store_true",  help="Skip visualisation")

    args = parser.parse_args()

    # ── Run ───────────────────────────────────────────────────────────────────
    scenario_fn = SCENARIOS[args.scenario]

    if args.scenario == "baseline":
        model = scenario_fn(args.steps, args.seed)
    else:
        model = scenario_fn(args.steps, args.seed, args.shock_step)

    # ── Save outputs ──────────────────────────────────────────────────────────
    metrics_path, nodes_path = save_outputs(model, _OUT)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  RUN SUMMARY")
    print("="*60)
    for k, v in model.summary().items():
        print(f"  {k:<30} {v}")

    # ── Visualise ─────────────────────────────────────────────────────────────
    if not args.no_viz:
        try:
            from visualize import generate_all_figures
            generate_all_figures(model, metrics_path, nodes_path, _FIG)
        except ImportError:
            print("\n[run.py] visualize.py not yet available — skipping figures")
        except Exception as e:
            print(f"\n[run.py] Visualisation error (non-fatal): {e}")

    print("\n[run.py] Done.")


if __name__ == "__main__":
    main()

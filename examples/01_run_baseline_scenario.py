"""
Example 1: Run the baseline (no-trigger) scenario and print summary metrics.

Run from repo root: PYTHONPATH=model/src python3 examples/01_run_baseline_scenario.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model", "src"))

from model import FoodEnergyModel
from stc_engine import STCEngine

model = FoodEnergyModel(scenario="example_baseline", seed=42, init_year=2022)
model.stc_engine = STCEngine(triggers=[], ss_mode="multiplicative")
model.run(15, verbose=False)

summary = model.summary()
print("Baseline scenario (2022, 15 steps, no triggers):")
for k, v in summary.items():
    print(f"  {k}: {v}")

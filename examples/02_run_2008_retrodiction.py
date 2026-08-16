"""
Example 2: Run the 2008 food price crisis retrodiction and compare to
real historical values.

Run from repo root: PYTHONPATH=model/src python3 examples/02_run_2008_retrodiction.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model", "src"))

from model import FoodEnergyModel
from stc_engine import STCEngine, triggers_2008_food_energy

model = FoodEnergyModel(scenario="example_2008", seed=42, init_year=2000)
model.stc_engine = STCEngine(
    triggers=[dict(t) for t in triggers_2008_food_energy(step_offset=-7)],
    ss_mode="multiplicative",
)
model.run(25, verbose=False)

summary = model.summary()
REAL_2008_FPI = 1.177  # normalised FAO Food Price Index, real historical value
model_fpi = summary["max_price_index"]
error_pct = abs(model_fpi - REAL_2008_FPI) / REAL_2008_FPI * 100

print(f"Model peak FPI (this single seed=42 run):  {model_fpi:.3f}")
print(f"Real 2008 FPI:                              {REAL_2008_FPI:.3f}")
print(f"Error (this run):                           {error_pct:.1f}%")
print()
print("NOTE: this is a single-seed illustrative run, not the scored")
print("retrodiction result. The authoritative figure (README.md's")
print("Validation status table, 41.15% error) is the MEAN of 30 Monte")
print("Carlo replicas computed by retrodiction.py::run_phase8 -- a single")
print("seed will differ, sometimes considerably, due to the model's")
print("stochastic elements. Run model/src/regenerate_all.py or call")
print("run_phase8() directly (see INSTALL.md) for the authoritative number.")

"""
Example 3: Search for the best policy combination against a moderate
climate+geopolitical shock, then find which countries a food-aid
intervention should target.

Run from repo root: PYTHONPATH=model/src python3 examples/03_run_policy_search.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model", "src"))

from scenarios import policy_search, node_level_policy_search

triggers = [
    {"name": "example_shock", "step": 5, "type": "climate", "scope": 0.30,
     "severity": 0.45, "food_shock": 1.25, "energy_shock": 1.10, "target_node": None},
]

print("=== General policy search ===")
result = policy_search(triggers=triggers, n_steps=15, n_random=10, verbose=True)
print(f"\nBest policy: {result['ranked_policies'][0]['label']}, "
      f"{result['ranked_policies'][0]['population_saved_millions']}M people saved\n")

print("=== Node-level search: which countries should receive food aid? ===")
node_result = node_level_policy_search(
    lever_type="food_aid",
    node_pool=["United States", "Argentina", "Canada", "Pakistan",
               "Central Africa", "East Africa", "Egypt"],
    triggers=triggers, n_steps=15, n_random=10, verbose=True,
)

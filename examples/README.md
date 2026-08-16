# Examples

All three scripts below were run and their output verified during this
consolidation pass (not written from assumption).

1. `01_run_baseline_scenario.py` — simplest possible usage: construct a
   model, run it, print the summary metrics.
2. `02_run_2008_retrodiction.py` — run a real historical scenario and
   compare against the real 2008 FAO Food Price Index value. **Read the
   printed note**: a single-seed run differs from the scored,
   Monte-Carlo-averaged retrodiction figure quoted in `README.md`.
3. `03_run_policy_search.py` — run both the general policy search and a
   node-level ("which countries should receive food aid") search.

Run any of them from the repository root:
```bash
PYTHONPATH=model/src python3 examples/01_run_baseline_scenario.py
```

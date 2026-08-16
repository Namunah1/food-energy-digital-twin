# scripts/

Standalone reproducibility and investigation scripts. Each can be run
directly with `python3 <script>.py` from `model/src/` (they import
sibling modules by relative same-directory import, matching this
project's existing convention — not installed as a package).

- `run_phase2_catalogue.py` — regenerates the full historical +
  counterfactual scenario catalogue (docs/scenarios/SCENARIO_CATALOGUE.md)
  with real Monte Carlo runs. ~3 minutes.
- `phase2_5_ablation.py` — the controlled single-mechanism ablation
  battery that diagnosed the premature-overload finding
  (docs/validation/PHASE2_5_BASELINE_STABILITY_INVESTIGATION.md).
- The master data-regeneration entrypoint (`regenerate_all.py`,
  producing every file in `data/processed/`) lives in `model/src/`
  rather than here, since it is imported-style tightly coupled to the
  other model modules — see `model/README.md`.

Run from `model/src/`: `python3 ../../scripts/run_phase2_catalogue.py`
would break the relative imports; copy the script into `model/src/`
first, or set `PYTHONPATH` to `model/src/`. This is a known convention
inherited from the original codebase, not a new limitation introduced
during this consolidation — flagged in LIMITATIONS.md.

## Near-duplicate found during consolidation, resolved by relocation

`regenerate_all_SMOKETEST.py` (originally `dev_tools_regenerate_all_FASTTEST.py`,
found living inside `model/src/` where nothing imported it) is a 12-line
variant of `model/src/regenerate_all.py` with reduced iteration counts
(`N_STEPS_MAIN=6` vs. `30`, etc.) for fast local smoke-testing during
development. Kept (not deleted — it's a real, working, occasionally
useful tool) but moved here since it is a script, not a model module,
and nothing in the codebase imports it. If you need a smoke-test run,
copy it into `model/src/` temporarily (same import-convention caveat as
every other script in this directory) or run it with `PYTHONPATH` set.
